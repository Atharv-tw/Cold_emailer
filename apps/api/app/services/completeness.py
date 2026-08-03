"""How much of a profile there is to write an email from.

This gates target creation, and the gate is the point. A cold email generated
from an empty profile is not a worse email, it is a useless one: the model has
nothing specific to say, so it writes filler, and filler sent to a stranger is
the exact thing this product exists to avoid.

The weights are not arbitrary. A headline and a bio are what the first
sentence is built from; one concrete project or role is what stops the mail
being generic; a link is the single URL the email is allowed. Availability
matters for internships and is worth prompting for, but nobody should be
blocked on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Below this, target creation is refused rather than discouraged.
REQUIRED_SCORE = 70


@dataclass(frozen=True)
class Requirement:
    key: str
    weight: int
    prompt: str


REQUIREMENTS = (
    Requirement("headline", 20, "One line on what you do - this opens the email."),
    Requirement("bio", 20, "Two or three sentences about you."),
    Requirement("evidence", 30, "At least one project or role. Without one the email has nothing concrete to point at."),
    Requirement("links", 15, "A portfolio, GitHub or LinkedIn - the one link the email is allowed."),
    Requirement("education", 10, "Where you studied, if it is relevant."),
    Requirement("availability", 5, "When you could start. Useful for internship and freelance outreach."),
)


@dataclass(frozen=True)
class Completeness:
    score: int
    complete: bool
    missing: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    @property
    def blocks_targets(self) -> bool:
        return not self.complete


def _present(profile, projects: list, experience: list) -> dict[str, bool]:
    links = profile.links or {}
    return {
        "headline": bool((profile.headline or "").strip()),
        "bio": bool((profile.bio or "").strip()),
        "evidence": bool(projects or experience),
        "links": any(str(value).strip() for value in links.values()),
        "education": bool((profile.education or "").strip()),
        "availability": bool((profile.availability or "").strip()),
    }


def assess(profile, projects: list, experience: list) -> Completeness:
    present = _present(profile, projects, experience)
    score = sum(r.weight for r in REQUIREMENTS if present[r.key])
    missing = [r.key for r in REQUIREMENTS if not present[r.key]]
    prompts = [r.prompt for r in REQUIREMENTS if not present[r.key]]
    return Completeness(
        score=score,
        complete=score >= REQUIRED_SCORE,
        missing=missing,
        prompts=prompts,
    )
