"""Merge fields, spintax, and deliverability linting.

Syntax
------
``{{first_name}}``            required merge field
``{{first_name|there}}``      merge field with a fallback when empty
``{a|b|c}``                   spintax - one option chosen at random

Merge values are substituted *after* spintax runs, so a value that happens to
contain braces can never be re-spun.

In the product the user never types a merge field; the model writes the email
and the draft editor shows it. This module survives anyway because ``lint`` is
the warning surface in that editor, and because a generated draft is still run
through ``render`` - which makes a stray ``{{...}}`` in model output visible as
a missing field rather than shipping to a stranger verbatim.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Mapping

MERGE_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
SPIN_RE = re.compile(r"\{([^{}]+)\}")
PLACEHOLDER = "\x00M{}\x00"

# Legitimate technical terms that would otherwise trip the ALL-CAPS check.
TECH_ACRONYMS = {
    "LSTM", "BERT", "CUDA", "CNNS", "RNNS", "LLMS", "LLM", "GPUS", "TPUS",
    "REST", "JSON", "YAML", "HTML", "HTTP", "HTTPS", "SQL", "NOSQL", "ETL",
    "SAAS", "REPL", "CI", "CD", "API", "APIS", "PYTORCH", "RAG", "SLAM",
    "MLOPS", "AUTOML", "IMAGENET", "COCO", "MNIST", "SOTA", "ROC", "AUC",
    "GAN", "GANS", "VAE", "PPO", "SFT", "RLHF", "PHD", "MSC", "BSC", "CGPA",
    # Security, systems and institutions
    "DAST", "SAST", "SSRF", "SQLI", "IDOR", "MTTR", "RBAC", "OAUTH", "SAML",
    "IEEE", "ACM", "GGSIPU", "IIIT", "NPTEL", "GPS", "OCR", "CRUD", "GRPC",
    "WCAG", "SDLC", "GDPR", "HIPAA", "SOC", "AES", "RSA", "JWT", "TLS",
}

# Words that reliably trip spam filters in cold outreach.
SPAM_TRIGGERS = [
    "act now", "buy now", "click here", "free trial", "guarantee",
    "limited time", "no obligation", "risk free", "special promotion",
    "100%", "cash bonus", "earn extra income", "make money", "order now",
    "this is not spam", "urgent", "winner", "congratulations",
]

# The generation prompt asks for under 900 characters. Warn a little above that
# so a draft that is merely a bit long does not nag, but a wall of text does.
LENGTH_WARNING_CHARS = 1200


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
    fields: Mapping[str, str],
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


def template_fields(text: str) -> dict[str, bool]:
    """Merge fields used in a template, mapped to whether they have a fallback."""
    found: dict[str, bool] = {}
    for token in MERGE_RE.findall(text):
        name, sep, fallback = token.partition("|")
        name = name.strip()
        if not name:
            continue
        has_fallback = bool(sep and fallback.strip())
        # A field is only optional if every use of it offers a fallback.
        found[name] = found.get(name, True) and has_fallback
    return found


def render_draft(
    subject: str | None,
    body: str,
    fields: Mapping[str, str],
    *,
    thread_subject: str | None = None,
    rng: random.Random | None = None,
) -> Rendered:
    """Render an editable draft into the text that would actually be sent.

    A follow-up with no subject of its own replies in the existing thread, so
    it inherits ``Re: <original>``. There is no footer: this is personal mail,
    and appending a compliance block to a personal note makes it read as a
    mass mailing.
    """
    missing: list[str] = []

    if subject and subject.strip():
        rendered_subject = render(subject, fields, rng=rng, missing=missing)
    elif thread_subject:
        rendered_subject = (
            thread_subject
            if thread_subject.lower().startswith("re:")
            else f"Re: {thread_subject}"
        )
    else:
        raise TemplateError("no subject, and no thread to reply to")

    rendered_body = render(body, fields, rng=rng, missing=missing).rstrip()
    return Rendered(
        subject=rendered_subject.strip(),
        body=rendered_body,
        missing=sorted(set(missing)),
    )


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

    if len(text) > LENGTH_WARNING_CHARS:
        warnings.append(f"{len(text)} chars - under ~900 reads better and replies better")

    if text.count("!") > 1:
        warnings.append("more than one exclamation mark")

    shouty = {
        word for word in re.findall(r"\b[A-Z]{4,}\b", text) if word not in TECH_ACRONYMS
    }
    if shouty:
        warnings.append(f"ALL-CAPS words: {', '.join(sorted(shouty))}")

    if "<img" in lowered or "<table" in lowered:
        warnings.append("HTML markup - plain text lands in the inbox more often")

    return warnings
