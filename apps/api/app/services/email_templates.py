"""Selectable generation templates.

These are not merge-field templates. They are compact briefs that steer the
model toward a proven structure while still forcing it to use the sender
profile and the specific target context. That is the right first version for
this product: the user picks an approach, but the email is still written for
one person.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailTemplate:
    key: str
    name: str
    description: str
    guidance: str


TEMPLATES: tuple[EmailTemplate, ...] = (
    EmailTemplate(
        key="specific_hook",
        name="Specific hook",
        description="Lead with what you noticed about them, then connect one proof point.",
        guidance=(
            "Structure: one sentence proving this was written for them; one sentence "
            "connecting the sender's most relevant evidence; one small ask. Use the "
            "target hook as the opening anchor."
        ),
    ),
    EmailTemplate(
        key="project_fit",
        name="Project fit",
        description="Lead with the sender's most relevant project for this recipient.",
        guidance=(
            "Structure: mention the recipient context briefly, then make the sender's "
            "most relevant project the concrete proof. Include at most one project link "
            "if it materially helps."
        ),
    ),
    EmailTemplate(
        key="recruiter_scan",
        name="Recruiter scan",
        description="Skimmable version for recruiters and hiring teams.",
        guidance=(
            "Structure: what the sender does, what they are looking for, one shipped "
            "proof point, availability, and a one-line ask. Prioritize clarity over charm."
        ),
    ),
    EmailTemplate(
        key="research_interest",
        name="Research interest",
        description="For professors, labs, papers, and technical research work.",
        guidance=(
            "Structure: name the work or topic the sender engaged with, state the sender's "
            "relevant background honestly, and ask one narrow question about fit or openings."
        ),
    ),
)


DEFAULT_TEMPLATE_KEY = "specific_hook"


def all_templates() -> tuple[EmailTemplate, ...]:
    return TEMPLATES


def template_for(key: str | None) -> EmailTemplate:
    wanted = (key or DEFAULT_TEMPLATE_KEY).strip()
    for template in TEMPLATES:
        if template.key == wanted:
            return template
    return TEMPLATES[0]
