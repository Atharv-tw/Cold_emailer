"""Turning a spreadsheet of leads into reviewed, importable rows.

This is the validation half of bulk import, and it is deliberately pure: it
takes a parsed grid plus the two sets that decide who may be added - the
addresses already on the user's list, and the addresses they have suppressed -
and returns a verdict per row. No database, no network, so the whole decision
table is testable without either.

The rule it enforces is the one `services.sheets` warned about: a bulk import
must not be a way around the checks single-add makes. So every row is held to
the same gates - a real address, not already on the list, not suppressed - and
the importer in the router adds the cross-user guard on top. What import does
*not* do is verify deliverability inline: a paid check per row would make a
large file slow and expensive, so imported targets carry a "checked before the
first send" marker and are verified lazily in the send path instead.

Categories, phrased for the person reviewing rather than as codes:

* ``ok``         - a real address with a hook; ready to write from.
* ``needs_hook`` - importable, but the one thing an email cannot be written
                   without is missing. Surfaced, not blocked, exactly as it is
                   for single-add.
* ``duplicate``  - already on the list, or a second copy within this file.
* ``suppressed`` - on the user's permanent do-not-contact list.
* ``invalid``    - no address, or one that is not an address.

Only ``ok`` and ``needs_hook`` are importable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schemas import COMPANY_TYPES, INTENTS, TARGET_TYPES
from .verification import normalise, syntax_ok

# The columns a file may feed. `linkedin` / `portfolio` / `github` / `other`
# are flattened here and folded back into the target's `links` at commit, so a
# spreadsheet can carry one link per column rather than a nested structure.
LINK_FIELDS = ("linkedin", "portfolio", "github", "other")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    required: bool = False


FIELDS: tuple[Field, ...] = (
    Field("name", "Name"),
    Field("email", "Email", required=True),
    Field("company", "Company"),
    Field("role", "Role"),
    Field("target_type", "Who they are"),
    Field("company_type", "Company type"),
    Field("intent", "What you want"),
    Field("hook", "Why them"),
    Field("timezone", "Timezone"),
    Field("linkedin", "LinkedIn"),
    Field("portfolio", "Portfolio"),
    Field("github", "GitHub"),
    Field("other", "Other link"),
)

FIELD_KEYS: tuple[str, ...] = tuple(f.key for f in FIELDS)


def mappable_fields() -> list[str]:
    """The field keys `sheets.suggest_mapping` maps headers onto."""
    return list(FIELD_KEYS)


# Loose synonyms for the three enum fields, so a column that says "Full-time"
# or "Big Tech" lands on the value the model actually stores. Anything the map
# does not recognise falls back to the field's default with a note, rather than
# rejecting the row over a label.
_ENUM_SYNONYMS: dict[str, str] = {
    # target_type
    "cofounder": "founder", "co-founder": "founder", "ceo": "founder", "cto": "founder",
    "hiring": "hiring_manager", "hiringmanager": "hiring_manager", "manager": "hiring_manager",
    "talent": "recruiter", "recruiting": "recruiter",
    "swe": "engineer", "developer": "engineer", "dev": "engineer", "eng": "engineer",
    "researcher": "professor", "prof": "professor", "academic": "professor",
    # company_type
    "artificialintelligence": "ai", "ml": "ai", "machinelearning": "ai",
    "education": "edtech", "edu": "edtech",
    "finance": "fintech", "financial": "fintech",
    "bigtech": "faang", "faanmg": "faang", "big_tech": "faang",
    "consultancy": "agency", "studio": "agency",
    "researchlab": "research_lab", "lab": "research_lab", "university": "research_lab",
    # intent
    "intern": "internship", "internships": "internship",
    "fulltime": "full_time", "full_time_role": "full_time", "job": "full_time",
    "contract": "freelance", "contracting": "freelance", "consulting": "freelance",
    "phd": "research", "researchrole": "research",
    "collaboration": "partnership", "collab": "partnership", "partner": "partnership",
    "advice": "feedback", "mentorship": "feedback",
}

_ENUM_DEFAULTS = {
    "target_type": ("founder", TARGET_TYPES),
    "company_type": ("other", COMPANY_TYPES),
    "intent": ("internship", INTENTS),
}


def _coerce_enum(field_key: str, raw: str) -> tuple[str, str | None]:
    """Return (value, note). `note` is set when the input had to be defaulted."""
    default, allowed = _ENUM_DEFAULTS[field_key]
    if not raw.strip():
        return default, None
    key = re.sub(r"[\s-]+", "_", raw.strip().lower())
    flat = key.replace("_", "")
    if key in allowed:
        return key, None
    if key in _ENUM_SYNONYMS:
        return _ENUM_SYNONYMS[key], None
    if flat in _ENUM_SYNONYMS:
        return _ENUM_SYNONYMS[flat], None
    return default, f"{raw.strip()!r} was not recognised, so {default!r} was used"


@dataclass
class ReviewRow:
    index: int  # 1-based position among the file's data rows
    values: dict[str, str]
    email: str
    status: str
    issues: list[str] = field(default_factory=list)

    @property
    def importable(self) -> bool:
        return self.status in ("ok", "needs_hook")


@dataclass
class ReviewResult:
    mapping: dict[str, str]  # header -> field key, as used
    unmapped_required: list[str]  # required field keys no column feeds
    rows: list[ReviewRow]

    def summary(self) -> dict[str, int]:
        counts = {
            "total": len(self.rows),
            "importable": 0,
            "needs_hook": 0,
            "duplicates": 0,
            "suppressed": 0,
            "invalid": 0,
        }
        for row in self.rows:
            if row.importable:
                counts["importable"] += 1
            if row.status == "needs_hook":
                counts["needs_hook"] += 1
            elif row.status == "duplicate":
                counts["duplicates"] += 1
            elif row.status == "suppressed":
                counts["suppressed"] += 1
            elif row.status == "invalid":
                counts["invalid"] += 1
        return counts


def _apply_mapping(row: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    """Pull a row's cells onto field keys, honouring the header->field mapping."""
    out: dict[str, str] = {key: "" for key in FIELD_KEYS}
    for header, field_key in mapping.items():
        if field_key in out:
            out[field_key] = (row.get(header) or "").strip()
    return out


def review(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    *,
    existing_emails: set[str],
    suppressed_emails: set[str],
) -> ReviewResult:
    """Classify every row against the same gates single-add applies.

    `existing_emails` and `suppressed_emails` are expected already normalised
    (lower-cased, trimmed); addresses seen earlier in this same file count as
    duplicates too, so a list that repeats someone is not imported twice.
    """
    unmapped_required = [
        f.key for f in FIELDS if f.required and f.key not in mapping.values()
    ]
    seen: set[str] = set()
    reviewed: list[ReviewRow] = []

    for position, raw in enumerate(rows, start=1):
        values = _apply_mapping(raw, mapping)
        email = normalise(values["email"])
        values["email"] = email
        issues: list[str] = []

        # Enum fields are coerced now so the preview shows what will be stored.
        for enum_key in _ENUM_DEFAULTS:
            values[enum_key], note = _coerce_enum(enum_key, values[enum_key])
            if note:
                issues.append(note)

        if not email:
            issues.insert(0, "no email address")
            status = "invalid"
        elif not syntax_ok(email):
            issues.insert(0, "not a valid email address")
            status = "invalid"
        elif email in suppressed_emails:
            issues.insert(0, "on your do-not-contact list")
            status = "suppressed"
        elif email in existing_emails or email in seen:
            issues.insert(0, "already on your list")
            status = "duplicate"
        elif not values["hook"].strip():
            issues.insert(0, "no reason for picking them - add one before writing")
            status = "needs_hook"
        else:
            status = "ok"

        if email and status in ("ok", "needs_hook"):
            seen.add(email)

        reviewed.append(ReviewRow(index=position, values=values, email=email, status=status, issues=issues))

    return ReviewResult(mapping=mapping, unmapped_required=unmapped_required, rows=reviewed)


def links_from(values: dict[str, str]) -> dict[str, str]:
    """The non-empty link columns, folded into the target's `links` shape."""
    return {key: values[key].strip() for key in LINK_FIELDS if values.get(key, "").strip()}


# The verification a bulk-imported target carries until the send path checks it.
# `unknown` never blocks a send (only `undeliverable` does), so this is visible
# and honest without pre-emptively refusing anyone; the real check happens in
# `sending.send_one` the first time a message is actually about to go out.
IMPORT_PENDING_VERIFICATION: dict[str, str] = {
    "status": "unknown",
    "reason": "import_pending",
    "detail": "Not checked yet - the address is verified before the first email is sent.",
    "source": "import",
    "checked_at": "",
}


def needs_import_verification(verification: dict | None) -> bool:
    """True for a target imported in bulk and not yet deliverability-checked."""
    return bool(verification) and verification.get("reason") == "import_pending"
