"""Request and response shapes.

Note what is absent from every input model here: `daily_cap`. The sending cap
is server-side and there is no setting that raises it, which means there must
be no field that carries one either - a limit you can talk the API into
changing is not a limit.
"""

from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from outreach_core.scheduling import DAY_NAMES, ScheduleError, SendingWindow


class LinksIn(BaseModel):
    portfolio: str = ""
    linkedin: str = ""
    github: str = ""
    other: str = ""


class SendingWindowIn(BaseModel):
    timezone: str = "UTC"
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
    highlights: list[str] = Field(default_factory=list)


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


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    parsed_at: Any = None
    original_kept: bool
