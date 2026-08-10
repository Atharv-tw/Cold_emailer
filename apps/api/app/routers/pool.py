"""The shared contact pool: browsing it, and taking someone out of it.

A pool contact is a `contacts` row with no owner. Row-level security makes it
readable by every signed-in user and writable by none, so this router never has
to check visibility itself - the policy already did. What it does have to do is
keep the pool honest about who is actually contactable: an address that has
hard-bounced for one user is not worth offering to the next.

Taking someone out of the pool copies them onto a `Target`. The catalogue entry
stays as it is - `targets` holds a snapshot, so correcting a company
description later does not rewrite what somebody already sent.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select

from ..deps import CurrentUser, Db, SettingsDep
from ..models import Contact, DeadAddress, Event, Target
from ..schemas import PoolContactOut, TargetOut
from .targets import _out, ensure_addable

router = APIRouter(prefix="/v1/pool", tags=["pool"])

# The pool may become a paid tier. This is deliberately a separate check from
# "is this contact public": visibility is a property of the data, access is a
# property of the account, and folding one into the other means reworking the
# schema the day pricing arrives.
async def require_pool_access(user) -> None:
    return None


def _contact_out(contact: Contact) -> PoolContactOut:
    return PoolContactOut(
        id=str(contact.id),
        name=contact.name,
        email=contact.email,
        role=contact.role,
        company=contact.company,
        company_description=contact.company_description,
        company_website=contact.company_website,
        target_type=contact.target_type,
        company_type=contact.company_type,
        timezone=contact.timezone,
        links=contact.links or {},
        verification=contact.verification or {},
    )


def pool_query(
    user_id: uuid.UUID,
    *,
    target_type: str | None = None,
    company_type: str | None = None,
    q: str | None = None,
):
    """The pool, minus everything this user could not usefully act on.

    Four exclusions, and each belongs here rather than in the UI because a
    contact the user cannot add should not be offered in the first place:

    * retired entries,
    * addresses a bounce has already proved do not exist,
    * addresses the loader could not find a mail exchanger for,
    * anyone already on this user's own list.

    No cross-user guard filtering: `RecipientGuard` is in monitor mode, so
    `blocked_emails` returns an empty set and the join would be dead weight. If
    enforcement is ever turned back on it belongs here too - otherwise a
    student clicks someone and gets a 409 from the add endpoint instead.

    Separate from the endpoint so the exclusions can be tested against a real
    database without standing up the request stack. They are the part worth
    testing: a wrong one silently offers a dead address to every user.
    """
    mine = select(Target.email).where(Target.user_id == user_id)

    query = (
        select(Contact)
        .where(Contact.owner_user_id.is_(None))
        .where(Contact.retired_at.is_(None))
        .where(Contact.verification["state"].astext != "undeliverable")
        .where(~Contact.email.in_(select(DeadAddress.email)))
        .where(~Contact.email.in_(mine))
    )

    if target_type:
        query = query.where(Contact.target_type == target_type)
    if company_type:
        query = query.where(Contact.company_type == company_type)
    if q and q.strip():
        # Escaped, so a company with a literal % or _ in its name does not
        # become a wildcard the user never typed.
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{term}%"
        query = query.where(
            or_(
                Contact.name.ilike(like, escape="\\"),
                Contact.company.ilike(like, escape="\\"),
                Contact.role.ilike(like, escape="\\"),
            )
        )

    return query.order_by(Contact.company, Contact.name)


@router.get("", response_model=list[PoolContactOut])
async def list_pool(
    user: CurrentUser,
    session: Db,
    target_type: str | None = Query(None),
    company_type: str | None = Query(None),
    q: str | None = Query(None, description="search over name, company and role"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PoolContactOut]:
    await require_pool_access(user)
    rows = await session.scalars(
        pool_query(user.id, target_type=target_type, company_type=company_type, q=q)
        .limit(limit)
        .offset(offset)
    )
    return [_contact_out(row) for row in rows]


@router.post("/{contact_id}/add", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
async def add_from_pool(
    contact_id: uuid.UUID, user: CurrentUser, session: Db, settings: SettingsDep
) -> TargetOut:
    """Copy a pool contact onto this user's list.

    `hook` is left empty on purpose. It is the one field that cannot be shared
    - the whole point of it is why *this* student picked *this* person - and
    prefilling it from the company description would put the same sentence in
    front of every founder at that company.
    """
    await require_pool_access(user)

    contact = await session.scalar(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.owner_user_id.is_(None),
            Contact.retired_at.is_(None),
        )
    )
    if contact is None:
        # Covers "no such id", "that one is private" and "it was retired" with
        # one answer: RLS already hid another user's row, so from here they are
        # the same thing.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That contact is not in the pool.")

    # Every gate single-add applies, from the one place they are written.
    await ensure_addable(session, user, contact.email, settings)

    target = Target(
        user_id=user.id,
        contact_id=contact.id,
        name=contact.name,
        email=contact.email,
        company=contact.company,
        role=contact.role,
        target_type=contact.target_type,
        company_type=contact.company_type,
        timezone=contact.timezone,
        links=contact.links or {},
        # Carried across rather than re-checked: the loader's MX pass is the
        # same verification a fresh add would start from, and re-running it per
        # user would be 499 identical lookups.
        verification=contact.verification or {},
        hook="",
        intent="internship",
        status="draft",
    )
    session.add(target)
    await session.flush()
    session.add(
        Event(
            user_id=user.id,
            target_id=target.id,
            type="target_created",
            detail=f"added from the shared pool ({contact.company})",
        )
    )
    await session.commit()
    return _out(target)
