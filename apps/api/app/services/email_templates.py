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
            "Within the three paragraphs: anchor the intro on the target hook, so the "
            "first paragraph could not have been sent to anyone else; make the work "
            "paragraph connect the sender's most relevant evidence to that hook; keep "
            "the ask small."
        ),
    ),
    EmailTemplate(
        key="project_fit",
        name="Project fit",
        description="Lead with the sender's most relevant project for this recipient.",
        guidance=(
            "Within the three paragraphs: keep the intro brief on the recipient's "
            "context, and make the work paragraph the sender's most relevant project "
            "as the concrete proof. Include at most one project link if it materially "
            "helps."
        ),
    ),
    EmailTemplate(
        key="recruiter_scan",
        name="Recruiter scan",
        description="Skimmable version for recruiters and hiring teams.",
        guidance=(
            "Within the three paragraphs: intro is what the sender does and what they "
            "are looking for; work is one shipped proof point; the ask carries the "
            "availability and one plain question. Prioritize clarity over charm."
        ),
    ),
    EmailTemplate(
        key="research_interest",
        name="Research interest",
        description="For professors, labs, papers, and technical research work.",
        guidance=(
            "Within the three paragraphs: the intro names the work or topic the sender "
            "engaged with; the work paragraph states the sender's relevant background "
            "honestly; the ask is one narrow question about fit or openings."
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
