"""The database schema.

Every user-owned table carries `user_id`, every query filters on it, and
Postgres row-level security enforces the same thing a second time. The
duplication is deliberate: the query filter is what makes the product correct,
and RLS is what makes a forgotten filter fail closed instead of leaking one
user's targets into another user's dashboard.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --------------------------------------------------------------------- identity


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    avatar: Mapped[str] = mapped_column(Text, default="")
    # A storage key, not a URL - set when the user uploads their own photo.
    # Empty means "use the Google picture in `avatar`" instead.
    avatar_override: Mapped[str] = mapped_column(Text, default="")

    # Set when Google tells us the grant is gone - a revoked token fails
    # silently on the next send, so the state has to be recorded explicitly.
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disconnected_reason: Mapped[str] = mapped_column(Text, default="")

    profile: Mapped["Profile | None"] = relationship(back_populates="user", uselist=False)


class GoogleToken(Base, TimestampMixin):
    """The refresh token, encrypted. Never returned by any endpoint."""

    __tablename__ = "google_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    refresh_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GmailWatch(Base, TimestampMixin):
    """State for the Gmail push subscription.

    `watch` expires about seven days out and then stops delivering with no
    error and no callback, so the expiry has to be tracked here and re-armed
    by a daily job. Nothing tells us when it lapses; that is the whole problem.
    """

    __tablename__ = "gmail_watch"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    history_id: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------- profile


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    headline: Mapped[str] = mapped_column(Text, default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    education: Mapped[str] = mapped_column(Text, default="")
    availability: Mapped[str] = mapped_column(Text, default="")

    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    sending_window: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # The server's ceiling for this user. There is no UI that raises it.
    daily_cap: Mapped[int] = mapped_column(Integer, default=20)
    first_send_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="profile")


class ProfileProject(Base, TimestampMixin):
    __tablename__ = "profile_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    tech: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    # A demo video, distinct from the live link - a recruiter with no time to
    # click through a live product will still watch ninety seconds of one.
    demo_url: Mapped[str] = mapped_column(Text, default="")
    highlights: Mapped[list[str]] = mapped_column(JSONB, default=list)
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    best_for: Mapped[list[str]] = mapped_column(JSONB, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ProfileExperience(Base, TimestampMixin):
    __tablename__ = "profile_experience"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(255), default="")
    started: Mapped[str] = mapped_column(String(32), default="")
    ended: Mapped[str] = mapped_column(String(32), default="")
    bullets: Mapped[list[str]] = mapped_column(JSONB, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Resume(Base, TimestampMixin):
    """Uploaded CV. The raw file is deleted after parsing unless kept."""

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), default="")
    storage_key: Mapped[str] = mapped_column(String(512), default="")
    parsed: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The user's explicit choice at upload time, not a default we assumed.
    keep_original: Mapped[bool] = mapped_column(Boolean, default=False)
    original_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------- targets


class Contact(Base, TimestampMixin):
    """A person who can be written to, and who - if anyone - owns that record.

    `owner_user_id` is the entire public/private mechanism, and it is one
    nullable column rather than a flag:

        NULL       in the shared pool. Every user reads it, no user writes it.
        a user id  private to that user.

    An enum alongside the owner would let the two disagree; a single column
    cannot. The asymmetric RLS policy in migration 0008 is what enforces the
    read/write split - `USING` admits public rows, `WITH CHECK` does not, so a
    request can see the pool but never write into it. Pool rows are written by
    the loader connecting as the schema owner, never by the application role.

    This is the catalogue. What a user has actually *done* about a contact
    lives on `Target`, because `status`, `gmail_thread_id` and `touches_sent`
    differ per user and cannot live on a row many users share.
    """

    __tablename__ = "contacts"
    __table_args__ = (
        # Private rows: one user cannot hold the same address twice. Public
        # rows have a NULL owner, which Postgres treats as distinct in a unique
        # constraint, so this does *not* dedupe the pool - the partial index in
        # 0008 does that.
        UniqueConstraint("owner_user_id", "email", name="uq_contacts_owner_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(255), default="")
    links: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # The company is denormalised onto the person on purpose. 253 companies to
    # 507 people is a small repeat, the pool is curated and changes rarely, and
    # a flat row maps straight onto the CSV import path that already exists.
    company: Mapped[str] = mapped_column(String(255), default="")
    company_description: Mapped[str] = mapped_column(Text, default="")
    company_website: Mapped[str] = mapped_column(Text, default="")

    target_type: Mapped[str] = mapped_column(String(64), default="")
    company_type: Mapped[str] = mapped_column(String(64), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="")

    # Verified once, for everyone. A pool contact found undeliverable is dead
    # for every user at the same moment - see `DeadAddress`.
    verification: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Identifier from whatever seeded this row, so re-running a loader updates
    # rather than duplicating. Empty for contacts a user typed in themselves.
    source_id: Mapped[str] = mapped_column(String(128), default="")
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeadAddress(Base):
    """Addresses that hard-bounced. Global, permanent, owned by nobody.

    Deliberately plaintext, which is a departure from `RecipientGuardRow`. That
    table is HMAC'd because it would otherwise be a record of *who this
    platform's users are contacting*. This one says only that a mailbox does
    not exist, and for pool contacts the address already sits in plaintext in
    `contacts` - hashing would buy nothing and would cost the ability to join.

    Only permanent failures (SMTP 5.x.x) belong here. A transient 4.x.x means a
    full mailbox or a greylisting server, and recording it would let one bad
    afternoon at a mail host burn a good contact for every user, forever.
    """

    __tablename__ = "dead_addresses"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Target(Base, TimestampMixin):
    """One user's outreach to one contact: the relationship, plus a snapshot.

    The person's details are copied here from `Contact` when the target is
    created, rather than read through the foreign key. That duplication is
    deliberate twice over:

    * `uq_targets_user_email` needs the address on this table. Keying only on
      `(user_id, contact_id)` would let a user hold the pool's contact for an
      address *and* a private contact for the same address, and write to the
      same person twice from the same account.
    * A target records what was actually sent. If the pool later corrects a
      company description, a thread already in flight should not retroactively
      claim the user wrote something they did not.
    """

    __tablename__ = "targets"
    __table_args__ = (
        # One user cannot hold the same address twice; two different users can.
        UniqueConstraint("user_id", "email", name="uq_targets_user_email"),
        # Nor reach the same catalogue entry twice. Both constraints are needed:
        # this one stops a contact being added twice, the one above stops the
        # same address arriving via two different contacts.
        UniqueConstraint("user_id", "contact_id", name="uq_targets_user_contact"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # The catalogue entry this was taken from. Nullable because targets created
    # before the pool existed have no entry, and `ondelete="SET NULL"` because
    # retiring a contact must not delete somebody's sent thread along with it.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )

    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    company: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(255), default="")

    # founder | hiring_manager | recruiter | engineer | professor
    target_type: Mapped[str] = mapped_column(String(64), default="")
    # edtech | ai | fintech | faang | agency | research_lab | other
    company_type: Mapped[str] = mapped_column(String(64), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="")

    # "What made you pick this person?" - free text. This is the old `specific`
    # merge field, asked in a way that needs no explanation.
    hook: Mapped[str] = mapped_column(Text, default="")
    # internship | full_time | freelance | research | partnership | feedback
    intent: Mapped[str] = mapped_column(String(64), default="")
    links: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # deliverable | risky | undeliverable | unknown, plus the reason.
    verification: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # draft | active | replied | bounced | opted_out | completed | paused
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    status_detail: Mapped[str] = mapped_column(Text, default="")

    gmail_thread_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Message-ID Gmail assigned to the last message we sent in this thread.
    last_message_id: Mapped[str] = mapped_column(Text, default="")
    thread_refs: Mapped[str] = mapped_column(Text, default="")
    thread_subject: Mapped[str] = mapped_column(Text, default="")

    touches_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    thread_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # A finished sequence may later start again. `touches_sent` resets to 0 and
    # the run is counted here instead, which is what keeps it inside the
    # `touches_sent <= MAX_TOUCHES` check constraint rather than climbing past
    # it.
    #
    # `cycles_used` counts sequences *completed*, not started - counting starts
    # would permit MAX_CYCLES + 1 runs, because the first was never counted.
    cycles_used: Mapped[int] = mapped_column(Integer, default=0)
    last_cycle_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["Message"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")

    gmail_message_id: Mapped[str] = mapped_column(String(64), default="")
    rfc822_message_id: Mapped[str] = mapped_column(Text, default="")

    # draft | queued | sent | failed
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default="")

    target: Mapped[Target] = relationship(back_populates="messages")


class ScheduleRow(Base, TimestampMixin):
    __tablename__ = "schedule"
    __table_args__ = (
        UniqueConstraint("target_id", "step", name="uq_schedule_target_step"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    # pending | claimed | done | cancelled
    state: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    # The mirrored Google Calendar reminder, if the user connected one. The
    # calendar is a synced layer, never the source of truth: this row decides
    # when the follow-up is due, and `event_synced_due_at` records the time the
    # calendar was last told so a moved due date can be detected and pushed.
    google_event_id: Mapped[str] = mapped_column(Text, default="")
    event_synced_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    detail: Mapped[str] = mapped_column(Text, default="")


class Suppression(Base):
    """Per-user opt-outs and bounces. Permanent by design."""

    __tablename__ = "suppression"
    __table_args__ = (UniqueConstraint("user_id", "email", name="uq_suppression_user_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecipientGuardRow(Base):
    """Cross-user pile-on guard.

    Not owned by any user, and deliberately holds no address: `email_key` is an
    HMAC under a secret that lives outside this database, so the table cannot
    be turned into a list of who the platform's users are contacting. See
    `outreach_core.limits.recipient_key`.
    """

    __tablename__ = "recipient_guard"

    email_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_contacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contact_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WorkerHeartbeat(Base):
    """A single row the worker touches each tick, so the app can tell it is up.

    Not user-scoped and carrying nothing private - just a timestamp per job -
    so it stays outside row-level security and any request can read whether the
    background worker ran recently. Without it, "is the worker running?" has no
    honest answer: an idle worker and a dead one look identical from the data.
    """

    __tablename__ = "worker_heartbeat"

    job: Mapped[str] = mapped_column(String(64), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")


class PushSubscription(Base, TimestampMixin):
    __tablename__ = "push_subs"
    __table_args__ = (UniqueConstraint("user_id", "endpoint", name="uq_push_user_endpoint"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    keys: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


# Tables carrying a user_id, used by the migration to switch RLS on uniformly
# rather than by a hand-maintained list that drifts from the models.
#
# `contacts` is deliberately absent. The uniform policy here is
# `user_id = current_setting(...)`, and a pool contact's owner is NULL, so
# under that predicate the entire shared pool would be invisible to everyone -
# silently, with no error. It gets its own asymmetric policy in 0008 instead.
#
# `dead_addresses`, `recipient_guard` and `worker_heartbeat` are absent because
# they belong to no user at all.
USER_SCOPED_TABLES = [
    "google_tokens", "gmail_watch", "profiles", "profile_projects",
    "profile_experience", "resumes", "targets", "messages", "schedule",
    "events", "suppression", "push_subs",
]
