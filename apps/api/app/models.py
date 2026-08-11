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

    # Whether this account may use the shared contact pool. Deliberately not
    # derived from anything: `owner_user_id IS NULL` says a contact is public,
    # which is a property of the data, and this says the account is allowed to
    # see it, which is a property of the billing relationship. Conflating them
    # means reworking the schema the day pricing changes.
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    # Set by hand, in SQL, and by nothing else. No endpoint reads this from a
    # payload or writes it, which is what stops the admin panel from being a
    # route to becoming an admin: there is no code path from "signed in" to
    # "privileged", so a bug in those handlers cannot manufacture one. The
    # first admin is a one-off UPDATE, and that chicken-and-egg is the point.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

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
    # When a notification last actually arrived. `expires_at` and
    # `last_checked_at` only record that Gmail accepted our `watch` call, which
    # says nothing about whether Pub/Sub can reach us: a subscription pointing
    # at a stale host or a route that no longer exists leaves both of those
    # looking perfectly healthy while every notification is dropped. That is
    # exactly how push stayed broken through a hosting migration, unnoticed,
    # until someone tested a reply by hand. This is the column that would have
    # said so.
    last_push_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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

    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
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


class TargetReply(Base, TimestampMixin):
    """The inbound message that ended a sequence, kept in full.

    Its own table rather than columns on `Target`, for one reason: a reply body
    is unbounded - a long answer quoting the whole thread runs to tens of
    kilobytes - and `select(Target)` fetches every column. Widening `targets`
    would put that text on the reconcile sweep, the target list, and the
    pre-send check, none of which ever read it. Here it is read only when
    someone opens the target that has one.

    Primary-keyed on `target_id`, which enforces one reply per target at the
    schema level. That matches the invariant, not just current behaviour:
    replying is terminal, and `may_schedule_touch` only lets a target start a
    new cycle when it is *silent*, so a target that answered can never come
    back around and answer twice.

    The body is stored because it has already been fetched and parsed - the
    classifier reads it to decide the verdict, then had been discarding it. Not
    a snippet: truncation would save nothing measurable here and would make the
    stored copy useless for the one thing it is for, which is reading what the
    person actually said.
    """

    __tablename__ = "target_replies"

    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), primary_key=True
    )
    # Denormalised from `targets` because the row-level security predicate is
    # `user_id = current_setting('app.user_id')` and every user-scoped table
    # carries its own copy. Reaching through the foreign key instead would need
    # a policy with a subquery on a table that has its own policy.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_email: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    gmail_message_id: Mapped[str] = mapped_column(String(64), default="")
    # When they sent it, from the message's own Date header - not when we
    # noticed. Those can differ by hours when push is down and the reconcile
    # sweep is what found it, and "replied 6 hours ago" is the true statement.
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class PaymentRequest(Base, TimestampMixin):
    """One claim that a user has paid, waiting to be believed.

    Payment happens entirely outside this system: the user scans a UPI QR, pays
    from their own bank app, and uploads a screenshot as evidence. Nothing here
    verifies money moved - an operator looks at the screenshot and decides. So
    this table is a queue of claims, not a ledger of payments, and `status` is
    a human's verdict rather than a gateway's.

    The screenshot itself lives in object storage; only its key is here. A
    presigned URL is minted per view and expires, so there is no long-lived
    link to an image that typically shows the payer's UPI handle, phone number
    and bank.

    **This table has no row-level security**, deliberately, which makes it the
    exception in this file. The operator has to list claims across all users,
    and the uniform policy is `user_id = current_setting('app.user_id')` - under
    which an unbound session sees zero rows rather than all of them, so there is
    no session that could serve that listing. Access is enforced in the router
    instead. The consequence is that **the user-facing read must filter by
    `user_id` in the query itself**: unlike everywhere else here, forgetting it
    fails open. If that trade stops being worth it, the shape to copy is
    `contacts` - per-command policies keyed on an `app.is_admin` setting bound
    alongside `app.user_id`.
    """

    __tablename__ = "payment_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # An object key, never a URL. URLs here expire; keys do not.
    screenshot_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Whatever reference the user chose to type. Not trusted, not parsed - it
    # exists so the operator can match a claim against a bank statement.
    upi_reference: Mapped[str] = mapped_column(String(255), default="")

    # pending | approved | rejected
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str] = mapped_column(Text, default="")

    # Why the notification email failed, if it did. The row is the record and
    # the email is only a nudge, so a failed send must not lose the claim - it
    # leaves a reason here and the request still appears in the panel.
    notify_error: Mapped[str] = mapped_column(Text, default="")


# Tables carrying a user_id, used by the migration to switch RLS on uniformly
# rather than by a hand-maintained list that drifts from the models.
#
# `contacts` is deliberately absent. The uniform policy here is
# `user_id = current_setting(...)`, and a pool contact's owner is NULL, so
# under that predicate the entire shared pool would be invisible to everyone -
# silently, with no error. It gets its own asymmetric policy in 0008 instead.
#
# `payment_requests` is absent for the opposite reason: it carries a `user_id`
# but must be readable across users by the operator, and no bound session can
# do that. See the docstring on `PaymentRequest` for what that costs.
#
# `dead_addresses`, `recipient_guard` and `worker_heartbeat` are absent because
# they belong to no user at all.
USER_SCOPED_TABLES = [
    "google_tokens", "gmail_watch", "profiles", "profile_projects",
    "profile_experience", "resumes", "targets", "target_replies", "messages",
    "schedule", "events", "suppression", "push_subs",
]
