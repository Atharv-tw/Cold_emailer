"""Merge fields, spintax, and the compliance footer.

Syntax
------
``{{first_name}}``            required merge field
``{{first_name|there}}``      merge field with a fallback when empty
``{a|b|c}``                   spintax - one option chosen at random

Merge values are substituted *after* spintax runs, so a value that happens to
contain braces can never be re-spun.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

MERGE_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
SPIN_RE = re.compile(r"\{([^{}]+)\}")
PLACEHOLDER = "\x00M{}\x00"

# Words that reliably trip spam filters in cold outreach.
SPAM_TRIGGERS = [
    "act now", "buy now", "click here", "free trial", "guarantee",
    "limited time", "no obligation", "risk free", "special promotion",
    "100%", "cash bonus", "earn extra income", "make money", "order now",
    "this is not spam", "urgent", "winner", "congratulations",
]


class TemplateError(Exception):
    pass


@dataclass
class Rendered:
    subject: str
    body: str
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing


def contact_fields(contact: sqlite3.Row | dict[str, Any]) -> dict[str, str]:
    """Flatten a contact row into the dict available to templates."""
    row = dict(contact)
    custom_raw = row.get("custom") or "{}"
    try:
        custom = json.loads(custom_raw) if isinstance(custom_raw, str) else dict(custom_raw)
    except (TypeError, ValueError):
        custom = {}

    fields: dict[str, str] = {k: str(v) for k, v in custom.items() if v is not None}
    for key in ("email", "first_name", "last_name", "company", "title", "campaign"):
        if row.get(key) is not None:
            fields[key] = str(row[key])

    first = fields.get("first_name", "").strip()
    last = fields.get("last_name", "").strip()
    fields.setdefault("full_name", f"{first} {last}".strip())
    return fields


def expand_spintax(text: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    # Innermost-first so nested spins resolve correctly.
    while True:
        match = SPIN_RE.search(text)
        if not match:
            return text
        options = match.group(1).split("|")
        text = text[: match.start()] + rng.choice(options).strip() + text[match.end() :]


def render(
    template: str,
    fields: dict[str, str],
    *,
    rng: random.Random | None = None,
    missing: list[str] | None = None,
) -> str:
    """Render one template string. Unknown fields are collected into `missing`."""
    missing = missing if missing is not None else []
    captured: list[str] = []

    def capture(match: re.Match[str]) -> str:
        token = match.group(1)
        name, _, fallback = token.partition("|")
        name = name.strip()
        value = (fields.get(name) or "").strip()
        if not value:
            if fallback.strip():
                value = fallback.strip()
            else:
                missing.append(name)
                value = ""
        captured.append(value)
        return PLACEHOLDER.format(len(captured) - 1)

    protected = MERGE_RE.sub(capture, template)
    spun = expand_spintax(protected, rng)
    for index, value in enumerate(captured):
        spun = spun.replace(PLACEHOLDER.format(index), value)
    return spun


def build_footer(identity, unsub_token: str = "") -> str:
    """CAN-SPAM footer: opt-out route plus a physical postal address."""
    lines = ["", "--", identity.unsubscribe_line]
    if identity.company:
        lines.append(f"{identity.company} · {identity.physical_address}")
    else:
        lines.append(identity.physical_address)
    return "\n".join(lines)


def render_step(
    step: dict[str, Any],
    contact: sqlite3.Row | dict[str, Any],
    identity,
    *,
    thread_subject: str | None = None,
    rng: random.Random | None = None,
    include_footer: bool = True,
) -> Rendered:
    """Render one sequence step for one contact."""
    fields = contact_fields(contact)
    missing: list[str] = []

    raw_subject = step.get("subject")
    if raw_subject:
        subject = render(str(raw_subject), fields, rng=rng, missing=missing)
    elif thread_subject:
        subject = thread_subject if thread_subject.lower().startswith("re:") else f"Re: {thread_subject}"
    else:
        raise TemplateError(
            f"step {step.get('id')} has no subject and there is no thread to reply to"
        )

    body = render(str(step.get("body", "")), fields, rng=rng, missing=missing)
    body = body.rstrip()
    if include_footer:
        body += "\n" + build_footer(identity, str(dict(contact).get("unsub_token", "")))

    return Rendered(subject=subject.strip(), body=body, missing=sorted(set(missing)))


def lint(text: str) -> list[str]:
    """Cheap deliverability warnings. Not a spam score, just obvious red flags."""
    warnings: list[str] = []
    lowered = text.lower()

    hits = [word for word in SPAM_TRIGGERS if word in lowered]
    if hits:
        warnings.append(f"spam trigger phrases: {', '.join(hits)}")

    links = re.findall(r"https?://\S+", text)
    if len(links) > 1:
        warnings.append(f"{len(links)} links - cold email should have at most one")

    if len(text) > 1200:
        warnings.append(f"{len(text)} chars - under ~900 reads better and replies better")

    if text.count("!") > 1:
        warnings.append("more than one exclamation mark")

    if re.search(r"\b[A-Z]{4,}\b", text):
        warnings.append("ALL-CAPS words")

    if "<img" in lowered or "<table" in lowered:
        warnings.append("HTML markup - plain text lands in the inbox more often")

    return warnings
