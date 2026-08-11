"""Request and response shapes.

Note what is absent from every input model here: `daily_cap`. The sending cap
is server-side and there is no setting that raises it, which means there must
be no field that carries one either - a limit you can talk the API into
changing is not a limit.
"""

from __future__ import annotations

from datetime import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from outreach_core.scheduling import DAY_NAMES, ScheduleError, SendingWindow


class LinksIn(BaseModel):
    # Every key the profile form offers has to be declared here. The router
    # rebuilds `profile.links` from this model's dump, and pydantic drops
    # undeclared fields without complaining - so a field missing from this
    # list is not rejected on save, it is silently discarded on every save.
    portfolio: str = ""
    linkedin: str = ""
    github: str = ""
    resume: str = ""
    other: str = ""


class SendingWindowIn(BaseModel):
    timezone: str = "Asia/Kolkata"
    start: time = time(9, 0)
    end: time = time(17, 0)
    days: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])

    @field_validator("days")
    @classmethod
    def _known_days(cls, value: list[str]) -> list[str]:
        lowered = [str(day).lower()[:3] for day in value]
        unknown = [day for day in lowered if day not in DAY_NAMES]
        if unknown:
            raise ValueError(f"unknown day(s): {', '.join(unknown)}")
        if not lowered:
            raise ValueError("pick at least one sending day")
        return lowered

    def to_core(self) -> SendingWindow:
        """Build the core object, which is where the real validation lives."""
        try:
            return SendingWindow(
                timezone=self.timezone,
                start=self.start,
                end=self.end,
                days=tuple(self.days),
            )
        except ScheduleError as exc:
            raise ValueError(str(exc)) from exc


class ProjectIn(BaseModel):
    name: str = ""
    summary: str = ""
    tech: str = ""
    url: str = ""
    demo_url: str = ""
    highlights: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    best_for: list[str] = Field(default_factory=list)


class ExperienceIn(BaseModel):
    company: str = ""
    role: str = ""
    started: str = ""
    ended: str = ""
    bullets: list[str] = Field(default_factory=list)


class ProfileIn(BaseModel):
    headline: str = ""
    bio: str = ""
    education: str = ""
    availability: str = ""
    links: LinksIn = Field(default_factory=LinksIn)
    sending_window: SendingWindowIn = Field(default_factory=SendingWindowIn)


class ProjectOut(ProjectIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class ExperienceOut(ExperienceIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class CompletenessOut(BaseModel):
    score: int
    complete: bool
    missing: list[str]
    prompts: list[str]


class ProfileOut(BaseModel):
    headline: str
    bio: str
    education: str
    availability: str
    links: dict[str, Any]
    sending_window: dict[str, Any]
    # Shown, never accepted. The user can see the ceiling they are under.
    daily_cap: int
    projects: list[ProjectOut]
    experience: list[ExperienceOut]
    completeness: CompletenessOut


class ParsedResumeOut(BaseModel):
    """A suggestion, not a saved profile.

    Everything here came out of a model reading a document, so it is returned
    for the user to confirm rather than written to their profile. The flag is
    part of the payload so the form can say where each value came from instead
    of presenting a guess as fact.
    """

    resume_id: str
    filename: str
    machine_extracted: bool = True
    original_kept: bool
    name: str = ""
    headline: str = ""
    bio: str = ""
    education: str = ""
    links: dict[str, str] = Field(default_factory=dict)
    projects: list[ProjectIn] = Field(default_factory=list)
    experience: list[ExperienceIn] = Field(default_factory=list)


# The form asks plain questions rather than offering merge fields. These are
# the answers, and the generator turns them into an email.
TARGET_TYPES = ("founder", "hiring_manager", "recruiter", "engineer", "professor")
COMPANY_TYPES = ("edtech", "ai", "fintech", "faang", "agency", "research_lab", "other")
INTENTS = ("internship", "full_time", "freelance", "research", "partnership", "feedback")


class TargetIn(BaseModel):
    name: str = ""
    email: EmailStr
    company: str = ""
    role: str = ""
    target_type: Literal[TARGET_TYPES] = "founder"  # type: ignore[valid-type]
    company_type: Literal[COMPANY_TYPES] = "other"  # type: ignore[valid-type]
    intent: Literal[INTENTS] = "internship"  # type: ignore[valid-type]
    timezone: str = ""
    # "What made you pick this person?" - the old `specific` merge field, asked
    # in a way that needs no explanation.
    hook: str = Field(default="", max_length=2000)
    links: LinksIn = Field(default_factory=LinksIn)


class TargetUpdate(BaseModel):
    """Everything optional, and no email field.

    Changing the address would carry the verification result, the touch count
    and the Gmail thread over to a different person. Delete and re-add instead.
    """

    name: str | None = None
    company: str | None = None
    role: str | None = None
    hook: str | None = None
    timezone: str | None = None
    target_type: Literal[TARGET_TYPES] | None = None  # type: ignore[valid-type]
    company_type: Literal[COMPANY_TYPES] | None = None  # type: ignore[valid-type]
    intent: Literal[INTENTS] | None = None  # type: ignore[valid-type]
    links: LinksIn | None = None


class TargetOut(BaseModel):
    id: str
    name: str
    email: str
    company: str
    role: str
    target_type: str
    company_type: str
    timezone: str
    hook: str
    intent: str
    links: dict[str, Any]
    verification: dict[str, Any]
    status: str
    status_detail: str
    touches_sent: int
    touches_remaining: int
    last_touch_at: Any = None
    can_send: bool
    blocked_reason: str
    # Deep link into the user's own Gmail. Empty until the first touch creates
    # a thread. Deliberately not accompanied by the reply body: this model is
    # also the list response, and a reply body on every row is exactly the
    # payload the separate `/reply` endpoint exists to keep out of it.
    gmail_thread_url: str = ""


class ReplyOut(BaseModel):
    """The inbound message that ended a sequence, in full.

    Its own endpoint rather than a field on `TargetOut`, so that listing two
    hundred targets does not carry two hundred reply bodies.
    """

    target_id: str
    from_email: str
    subject: str
    body: str
    received_at: Any = None
    read_at: Any = None
    gmail_thread_url: str = ""


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    parsed_at: Any = None
    original_kept: bool


# ------------------------------------------------------------------ bulk import


class PoolContactOut(BaseModel):
    """A shared-pool contact as the browse page sees it.

    No `hook` and no `status`: both belong to a user's outreach, not to the
    person, and a pool row has neither until somebody takes it.
    """

    id: str
    name: str
    email: str
    role: str
    company: str
    company_description: str
    company_website: str
    target_type: str
    company_type: str
    timezone: str
    links: dict[str, str]
    verification: dict[str, Any]


class PoolPageOut(BaseModel):
    """One page of the pool, and how many there are in total.

    The total is separate because it cannot be inferred from the page: a
    listing that returned 60 rows tells you nothing about whether 60 or 4,000
    matched. Without it the browse page can only describe what it was handed,
    which reads as "60 people" to somebody looking at a list of 499.
    """

    items: list[PoolContactOut]
    # Matching the filters, ignoring limit and offset.
    total: int


class ImportField(BaseModel):
    """One column an uploaded file may feed, named as the form asks it."""

    key: str
    label: str
    required: bool


class ImportRowOut(BaseModel):
    index: int  # 1-based row number among the file's data rows
    name: str
    email: str
    company: str
    role: str
    # ok | needs_hook | duplicate | suppressed | invalid
    status: str
    issues: list[str]
    importable: bool


class ImportSummary(BaseModel):
    total: int
    importable: int
    needs_hook: int
    duplicates: int
    suppressed: int
    # Hard-bounced for someone on this platform, so not importable by anyone.
    undeliverable: int = 0
    invalid: int


class ImportPreviewOut(BaseModel):
    headers: list[str]
    fields: list[ImportField]
    mapping: dict[str, str]  # header -> field key, as applied
    unmapped_required: list[str]
    rows: list[ImportRowOut]
    summary: ImportSummary


class ImportCommitOut(BaseModel):
    created: int
    skipped: int
    # reason -> count, so the user can see why anything was left out
    skipped_reasons: dict[str, int]
    summary: ImportSummary
