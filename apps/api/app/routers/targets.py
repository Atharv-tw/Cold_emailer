"""The people being written to.

Most of this file is refusals, and that is the shape the product should have.
Adding somebody is easy; the interesting behaviour is all the cases where the
answer is no and the user is told why in a sentence they can act on rather
than a validation code.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, status
from sqlalchemy import delete, or_, select

from outreach_core.limits import MAX_TOUCHES, TERMINAL_STATUSES, may_schedule_touch, remaining_touches

from .. import errors
from ..deps import CurrentUser, Db, SettingsDep
from ..errors import AppError
from ..models import Event, Profile, ProfileExperience, ProfileProject, Suppression, Target
from ..schemas import TargetIn, TargetOut, TargetUpdate
from ..services import guard
from ..services.completeness import assess
from ..services.replies import is_dead_address
from ..services.verification import EmailVerifier, normalise

router = APIRouter(prefix="/v1/targets", tags=["targets"])

# What a target's status means once the sequence is over, phrased for the user.
TERMINAL_EXPLANATIONS = {
    "replied": "They already replied, so the sequence stopped. Reply in your inbox instead.",
    "bounced": "Mail to that address bounced.",
    "opted_out": "They asked not to be contacted again.",
    "suppressed": "That address is on your suppression list.",
}


def _out(target: Target) -> TargetOut:
    verification = target.verification or {}
    # One decision, read twice below. Computed once so `can_send` and
    # `blocked_reason` cannot disagree about the same target.
    decision = may_schedule_touch(
        status=target.status,
        touches_sent=target.touches_sent,
        verification=verification.get("status"),
        cycles_used=target.cycles_used,
        last_cycle_ended_at=target.last_cycle_ended_at,
        now=datetime.now(timezone.utc),
    )
    return TargetOut(
        id=str(target.id),
        name=target.name,
        email=target.email,
        company=target.company,
        role=target.role,
        target_type=target.target_type,
        company_type=target.company_type,
        timezone=target.timezone,
        hook=target.hook,
        intent=target.intent,
        links=target.links or {},
        verification=verification,
        status=target.status,
        status_detail=target.status_detail,
        touches_sent=target.touches_sent,
        touches_remaining=remaining_touches(target.touches_sent),
        last_touch_at=target.last_touch_at,
        can_send=decision.allowed,
        blocked_reason=decision.reason,
    )


async def _require_usable_profile(session, user_id) -> None:
    profile = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    projects = list(
        await session.scalars(select(ProfileProject).where(ProfileProject.user_id == user_id))
    )
    experience = list(
        await session.scalars(select(ProfileExperience).where(ProfileExperience.user_id == user_id))
    )
    if profile is None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.PROFILE_INCOMPLETE,
            "Fill in your profile first - an email cannot be written without it.",
        )

    score = assess(profile, projects, experience)
    if score.blocks_targets:
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.PROFILE_INCOMPLETE,
            "Your profile is not complete enough to write from yet. Still needed: "
            + "; ".join(score.prompts),
        )


@router.get("", response_model=list[TargetOut])
async def list_targets(
    user: CurrentUser,
    session: Db,
    status_filter: str | None = Query(None, alias="status"),
    target_type: str | None = Query(None),
    company_type: str | None = Query(None),
    intent: str | None = Query(None),
    q: str | None = Query(None, description="search over name, company and email"),
) -> list[TargetOut]:
    """The list, narrowable by the same facets the target form offers.

    An unknown facet value simply matches nothing rather than being rejected:
    the filters are a convenience over one user's own rows, and a 422 on a
    stale query string would be a worse experience than an empty list.
    """
    query = select(Target).where(Target.user_id == user.id)
    if status_filter:
        query = query.where(Target.status == status_filter)
    if target_type:
        query = query.where(Target.target_type == target_type)
    if company_type:
        query = query.where(Target.company_type == company_type)
    if intent:
        query = query.where(Target.intent == intent)
    if q and q.strip():
        # ILIKE with the term escaped, so a name with a literal % or _ does not
        # turn into a wildcard the user did not type.
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{term}%"
        query = query.where(
            or_(
                Target.name.ilike(like, escape="\\"),
                Target.company.ilike(like, escape="\\"),
                Target.email.ilike(like, escape="\\"),
            )
        )
    rows = await session.scalars(query.order_by(Target.created_at.desc()))
    return [_out(row) for row in rows]


async def ensure_addable(session, user, email: str, settings) -> None:
    """Every gate a new target must pass, wherever it came from.

    Shared by single-add and by taking someone out of the shared pool. The two
    entry points must not be allowed to drift: these checks are what stop a
    user writing to the same person twice, or to someone who asked to be left
    alone, and a second code path that forgot one of them would not fail
    loudly - it would just quietly send the email.
    """
    if email == normalise(user.email):
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors.OWN_ADDRESS,
            "That is your own address.",
        )

    await _require_usable_profile(session, user.id)

    # A permanent opt-out is permanent. Re-adding is refused with the reason,
    # not silently accepted and then blocked at send time - the user should
    # find out now, while they still remember who this is.
    suppressed = await session.scalar(
        select(Suppression).where(Suppression.user_id == user.id, Suppression.email == email)
    )
    if suppressed is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.SUPPRESSED,
            f"You cannot contact {email} again: {suppressed.reason or 'they opted out'}.",
        )

    # Dead for everyone, not just for this user. Refused at add time for the
    # same reason a suppression is: finding out now beats finding out six days
    # later when the send fails.
    if await is_dead_address(session, email):
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.DEAD_ADDRESS,
            f"{email} does not exist - mail to it has already hard-bounced. "
            "Check the address, or pick someone else.",
        )

    existing = await session.scalar(
        select(Target).where(Target.user_id == user.id, Target.email == email)
    )
    if existing is not None:
        if existing.status in TERMINAL_STATUSES:
            raise AppError(
                status.HTTP_409_CONFLICT,
                errors.SEQUENCE_ENDED,
                TERMINAL_EXPLANATIONS.get(existing.status, f"That sequence ended ({existing.status}).")
                + " Re-adding them is not possible.",
            )
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.DUPLICATE_TARGET,
            f"{email} is already on your list"
            + (f" ({existing.touches_sent} of {MAX_TOUCHES} touches sent)." if existing.touches_sent else "."),
        )

    # Cross-user guard. Checked here as well as at send time so the user is not
    # told six days later that this one was never going to go out. Currently in
    # monitor mode, so this returns False - see services/guard.py.
    if await guard.is_blocked(session, email, settings.recipient_guard_secret_bytes):
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.GUARD_BLOCKED,
            "That person is being contacted by a lot of accounts here at the "
            "moment, so this platform is not sending them anything further "
            "right now. Try again in a week.",
        )


@router.post("", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
async def create_target(
    payload: TargetIn, user: CurrentUser, session: Db, settings: SettingsDep
) -> TargetOut:
    email = normalise(payload.email)
    await ensure_addable(session, user, email, settings)

    verifier = EmailVerifier(
        api_key=settings.quickemailverification_api_key,
        endpoint=settings.quickemailverification_endpoint,
    )
    verification = await verifier.verify(email)

    target = Target(
        user_id=user.id,
        name=payload.name.strip(),
        email=email,
        company=payload.company.strip(),
        role=payload.role.strip(),
        target_type=payload.target_type,
        company_type=payload.company_type,
        timezone=payload.timezone.strip(),
        hook=payload.hook.strip(),
        intent=payload.intent,
        links={k: v.strip() for k, v in payload.links.model_dump().items() if v.strip()},
        verification=verification.to_json(),
        status="draft",
        status_detail=verification.detail if verification.blocks_sending else "",
    )
    session.add(target)
    await session.flush()
    session.add(
        Event(
            user_id=user.id,
            target_id=target.id,
            type="target_created",
            # Nothing at all when the checker is switched off. "verification:
            # unknown (verification_not_configured)" is a fact about the
            # deployment, not about this address, and the history is a record
            # of what happened to this person. The banner on the target page
            # suppresses the same verdict for the same reason.
            detail=(
                ""
                if verification.reason == "verification_not_configured"
                else f"verification: {verification.status} ({verification.reason})"
            ),
        )
    )
    await session.commit()
    return _out(target)


@router.get("/{target_id}", response_model=TargetOut)
async def read_target(target_id: uuid.UUID, user: CurrentUser, session: Db) -> TargetOut:
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user.id)
    )
    if target is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, errors.TARGET_NOT_FOUND, "That contact is no longer on your list."
        )
    return _out(target)


@router.patch("/{target_id}", response_model=TargetOut)
async def update_target(
    target_id: uuid.UUID, payload: TargetUpdate, user: CurrentUser, session: Db
) -> TargetOut:
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user.id)
    )
    if target is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, errors.TARGET_NOT_FOUND, "That contact is no longer on your list."
        )
    if target.status in TERMINAL_STATUSES:
        raise AppError(
            status.HTTP_409_CONFLICT,
            errors.SEQUENCE_ENDED,
            TERMINAL_EXPLANATIONS.get(target.status, "That sequence has ended."),
        )

    # The address is deliberately not editable. Changing it would carry the
    # verification result, the touch count and the thread across to a different
    # person; deleting and re-adding makes that impossible.
    for field in ("name", "company", "role", "hook", "timezone"):
        value = getattr(payload, field)
        if value is not None:
            setattr(target, field, value.strip())
    for field in ("target_type", "company_type", "intent"):
        value = getattr(payload, field)
        if value is not None:
            setattr(target, field, value)
    if payload.links is not None:
        target.links = {k: v.strip() for k, v in payload.links.model_dump().items() if v.strip()}

    await session.commit()
    return _out(target)


@router.post("/{target_id}/reverify", response_model=TargetOut)
async def reverify(
    target_id: uuid.UUID, user: CurrentUser, session: Db, settings: SettingsDep
) -> TargetOut:
    """Check an address again.

    Worth having because "unknown" is often a transient answer - the checker
    was rate limited or out of credits - and a user should not have to delete
    and re-add a target to get a second opinion.
    """
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user.id)
    )
    if target is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, errors.TARGET_NOT_FOUND, "That contact is no longer on your list."
        )

    verifier = EmailVerifier(
        api_key=settings.quickemailverification_api_key,
        endpoint=settings.quickemailverification_endpoint,
    )
    verification = await verifier.verify(target.email)
    target.verification = verification.to_json()
    target.status_detail = verification.detail if verification.blocks_sending else ""
    await session.commit()
    return _out(target)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(target_id: uuid.UUID, user: CurrentUser, session: Db) -> None:
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user.id)
    )
    if target is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, errors.TARGET_NOT_FOUND, "That contact is no longer on your list."
        )

    # Deleting a target does not delete a suppression. Someone who asked not to
    # be contacted stays that way whatever happens to the row that recorded it.
    await session.execute(delete(Target).where(Target.id == target.id))
    await session.commit()


@router.post("/{target_id}/stop", response_model=TargetOut)
async def stop_target(
    target_id: uuid.UUID, user: CurrentUser, session: Db, suppress: bool = Query(False)
) -> TargetOut:
    """Stop a sequence by hand, optionally never contacting them again."""
    target = await session.scalar(
        select(Target).where(Target.id == target_id, Target.user_id == user.id)
    )
    if target is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, errors.TARGET_NOT_FOUND, "That contact is no longer on your list."
        )

    target.status = "opted_out" if suppress else "paused"
    target.status_detail = "stopped by you"
    if suppress:
        await _suppress(session, user.id, target.email, "you asked not to contact them again")
    session.add(
        Event(user_id=user.id, target_id=target.id, type="stopped", detail=target.status)
    )
    await session.commit()
    return _out(target)


async def _suppress(session, user_id: uuid.UUID, email: str, reason: str) -> None:
    """Add to the user's suppression list. Idempotent, and never removed here.

    There is no endpoint that deletes a suppression, and that is deliberate.
    """
    existing = await session.scalar(
        select(Suppression).where(Suppression.user_id == user_id, Suppression.email == email)
    )
    if existing is None:
        session.add(
            Suppression(user_id=user_id, email=email, reason=reason, at=datetime.now(timezone.utc))
        )
