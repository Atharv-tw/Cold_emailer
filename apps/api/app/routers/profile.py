"""The profile the email gets written from."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from ..deps import CurrentUser, Db, SettingsDep
from ..models import Profile, ProfileExperience, ProfileProject, Resume
from ..schemas import (
    CompletenessOut,
    ExperienceIn,
    ProfileIn,
    ProfileOut,
    ProjectIn,
)
from ..services.completeness import assess
from ..services.storage import LocalStorage

router = APIRouter(prefix="/v1/profile", tags=["profile"])


async def _load(session, user_id) -> tuple[Profile, list[ProfileProject], list[ProfileExperience]]:
    profile = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        # Created at sign-in; a missing one means the row was removed underneath us.
        profile = Profile(user_id=user_id)
        session.add(profile)
        await session.flush()

    projects = list(
        await session.scalars(
            select(ProfileProject)
            .where(ProfileProject.user_id == user_id)
            .order_by(ProfileProject.position)
        )
    )
    experience = list(
        await session.scalars(
            select(ProfileExperience)
            .where(ProfileExperience.user_id == user_id)
            .order_by(ProfileExperience.position)
        )
    )
    return profile, projects, experience


def _out(profile, projects, experience) -> ProfileOut:
    score = assess(profile, projects, experience)
    return ProfileOut(
        headline=profile.headline,
        bio=profile.bio,
        education=profile.education,
        availability=profile.availability,
        links=profile.links or {},
        sending_window=profile.sending_window or {},
        daily_cap=profile.daily_cap,
        projects=[
            {
                "id": str(p.id),
                "name": p.name,
                "summary": p.summary,
                "tech": p.tech,
                "url": p.url,
                "highlights": p.highlights or [],
                "categories": p.categories or [],
                "best_for": p.best_for or [],
            }
            for p in projects
        ],
        experience=[
            {
                "id": str(e.id),
                "company": e.company,
                "role": e.role,
                "started": e.started,
                "ended": e.ended,
                "bullets": e.bullets or [],
            }
            for e in experience
        ],
        completeness=CompletenessOut(
            score=score.score,
            complete=score.complete,
            missing=score.missing,
            prompts=score.prompts,
        ),
    )


@router.get("", response_model=ProfileOut)
async def read_profile(user: CurrentUser, session: Db) -> ProfileOut:
    profile, projects, experience = await _load(session, user.id)
    return _out(profile, projects, experience)


@router.put("", response_model=ProfileOut)
async def update_profile(payload: ProfileIn, user: CurrentUser, session: Db) -> ProfileOut:
    profile, projects, experience = await _load(session, user.id)

    try:
        window = payload.sending_window.to_core()
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    profile.headline = payload.headline.strip()
    profile.bio = payload.bio.strip()
    profile.education = payload.education.strip()
    profile.availability = payload.availability.strip()
    profile.links = {k: v.strip() for k, v in payload.links.model_dump().items() if v.strip()}
    profile.timezone = window.timezone
    profile.sending_window = {
        "timezone": window.timezone,
        "start": window.start.isoformat(timespec="minutes"),
        "end": window.end.isoformat(timespec="minutes"),
        "days": list(window.days),
    }
    # daily_cap is deliberately not read from the payload.

    await session.commit()
    return _out(profile, projects, experience)


@router.put("/projects", response_model=ProfileOut)
async def replace_projects(
    payload: list[ProjectIn], user: CurrentUser, session: Db
) -> ProfileOut:
    await session.execute(delete(ProfileProject).where(ProfileProject.user_id == user.id))
    for position, item in enumerate(payload):
        if not item.name.strip():
            continue
        session.add(
            ProfileProject(
                user_id=user.id,
                name=item.name.strip(),
                summary=item.summary.strip(),
                tech=item.tech.strip(),
                url=item.url.strip(),
                demo_url=item.demo_url.strip(),
                highlights=[h for h in item.highlights if h.strip()],
                categories=[c.strip().lower() for c in item.categories if c.strip()],
                best_for=[b.strip().lower() for b in item.best_for if b.strip()],
                position=position,
            )
        )
    await session.commit()
    profile, projects, experience = await _load(session, user.id)
    return _out(profile, projects, experience)


@router.put("/experience", response_model=ProfileOut)
async def replace_experience(
    payload: list[ExperienceIn], user: CurrentUser, session: Db
) -> ProfileOut:
    await session.execute(delete(ProfileExperience).where(ProfileExperience.user_id == user.id))
    for position, item in enumerate(payload):
        if not item.company.strip():
            continue
        session.add(
            ProfileExperience(
                user_id=user.id,
                company=item.company.strip(),
                role=item.role.strip(),
                started=item.started.strip(),
                ended=item.ended.strip(),
                bullets=[b for b in item.bullets if b.strip()],
                position=position,
            )
        )
    await session.commit()
    profile, projects, experience = await _load(session, user.id)
    return _out(profile, projects, experience)


@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_data(user: CurrentUser, session: Db, settings: SettingsDep) -> None:
    """Delete every resume and everything extracted from one.

    This is the button the upload screen promises, so it removes the files
    from storage as well as the rows - a delete that leaves the PDF on disk
    would make that promise false.
    """
    LocalStorage(settings.storage_dir).delete_prefix(str(user.id))
    await session.execute(delete(Resume).where(Resume.user_id == user.id))
    await session.execute(delete(ProfileProject).where(ProfileProject.user_id == user.id))
    await session.execute(delete(ProfileExperience).where(ProfileExperience.user_id == user.id))

    profile = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is not None:
        profile.headline = ""
        profile.bio = ""
        profile.education = ""
        profile.availability = ""
        profile.links = {}
    await session.commit()
