"""SQLite persistence: contacts, queued messages, events, opens."""

from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY,
    email           TEXT NOT NULL COLLATE NOCASE UNIQUE,
    first_name      TEXT DEFAULT '',
    last_name       TEXT DEFAULT '',
    company         TEXT DEFAULT '',
    title           TEXT DEFAULT '',
    custom          TEXT DEFAULT '{}',
    campaign        TEXT DEFAULT '',
    sequence        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    mailbox_id      TEXT,
    next_step       INTEGER NOT NULL DEFAULT 1,
    next_due_at     TEXT,
    thread_subject  TEXT,
    thread_refs     TEXT DEFAULT '',
    last_msgid      TEXT,
    unsub_token     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contacts_due
    ON contacts (status, next_due_at);
CREATE INDEX IF NOT EXISTS idx_contacts_sequence
    ON contacts (sequence, status);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY,
    contact_id   INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    step         INTEGER NOT NULL,
    mailbox_id   TEXT NOT NULL,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    msgid        TEXT,
    in_reply_to  TEXT,
    status       TEXT NOT NULL,
    sent_at      TEXT,
    error        TEXT,
    track_token  TEXT,
    attempts     INTEGER NOT NULL DEFAULT 1,
    UNIQUE (contact_id, step)
);

CREATE INDEX IF NOT EXISTS idx_messages_sent
    ON messages (mailbox_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_messages_msgid ON messages (msgid);
CREATE INDEX IF NOT EXISTS idx_messages_token ON messages (track_token);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    at         TEXT NOT NULL,
    detail     TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events (type, at);

CREATE TABLE IF NOT EXISTS opens (
    id          INTEGER PRIMARY KEY,
    track_token TEXT NOT NULL,
    at          TEXT NOT NULL,
    user_agent  TEXT DEFAULT '',
    ip          TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS mailbox_state (
    mailbox_id      TEXT PRIMARY KEY,
    next_allowed_at TEXT,
    last_sent_at    TEXT,
    first_send_date TEXT,
    imap_last_uid   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS suppression (
    email  TEXT PRIMARY KEY COLLATE NOCASE,
    reason TEXT DEFAULT '',
    at     TEXT NOT NULL
);
"""

# Terminal states: the sequence stops and no further mail goes out.
STOPPED_STATUSES = ("replied", "bounced", "unsubscribed", "completed", "paused")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime | None) -> str | None:
    return moment.astimezone(timezone.utc).isoformat() if moment else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    # ---------------------------------------------------------------- contacts

    def upsert_contact(self, row: dict[str, Any], sequence: str, campaign: str = "") -> tuple[int, bool]:
        """Insert a contact. Returns (contact_id, created). Existing rows are left alone."""
        email = (row.get("email") or "").strip().lower()
        if not email:
            raise ValueError("contact row has no email")

        known = {"email", "first_name", "last_name", "company", "title"}
        custom = {k: v for k, v in row.items() if k not in known and v not in (None, "")}
        now = iso(utcnow())

        existing = self.conn.execute(
            "SELECT id FROM contacts WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return existing["id"], False

        cursor = self.conn.execute(
            """
            INSERT INTO contacts (email, first_name, last_name, company, title,
                                  custom, campaign, sequence, status, next_step,
                                  next_due_at, unsub_token, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?)
            """,
            (
                email,
                (row.get("first_name") or "").strip(),
                (row.get("last_name") or "").strip(),
                (row.get("company") or "").strip(),
                (row.get("title") or "").strip(),
                json.dumps(custom),
                campaign,
                sequence,
                now,
                secrets.token_urlsafe(12),
                now,
                now,
            ),
        )
        return int(cursor.lastrowid), True

    def get_contact(self, contact_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()

    def find_contact_by_email(self, email: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM contacts WHERE email = ?", (email.strip().lower(),)
        ).fetchone()

    def due_contacts(self, now: datetime, limit: int = 200) -> list[sqlite3.Row]:
        """Active contacts whose next step is due, oldest first."""
        return self.conn.execute(
            """
            SELECT * FROM contacts
            WHERE status = 'active'
              AND next_due_at IS NOT NULL
              AND next_due_at <= ?
            ORDER BY next_due_at ASC
            LIMIT ?
            """,
            (iso(now), limit),
        ).fetchall()

    def set_contact_status(self, contact_id: int, status: str, detail: str = "") -> None:
        self.conn.execute(
            "UPDATE contacts SET status = ?, next_due_at = NULL, updated_at = ? WHERE id = ?",
            (status, iso(utcnow()), contact_id),
        )
        self.log_event(contact_id, status, detail)

    def advance_contact(
        self,
        contact_id: int,
        *,
        next_step: int,
        next_due_at: datetime | None,
        mailbox_id: str,
        thread_subject: str | None,
        msgid: str | None,
        thread_refs: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE contacts
               SET next_step = ?, next_due_at = ?, mailbox_id = ?,
                   thread_subject = COALESCE(thread_subject, ?),
                   last_msgid = ?, thread_refs = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                next_step,
                iso(next_due_at),
                mailbox_id,
                thread_subject,
                msgid,
                thread_refs,
                iso(utcnow()),
                contact_id,
            ),
        )

    def set_next_due(self, contact_id: int, when: datetime | None) -> None:
        self.conn.execute(
            "UPDATE contacts SET next_due_at = ?, updated_at = ? WHERE id = ?",
            (iso(when), iso(utcnow()), contact_id),
        )

    def counts_by_status(self, sequence: str | None = None) -> dict[str, int]:
        query = "SELECT status, COUNT(*) AS n FROM contacts"
        params: tuple = ()
        if sequence:
            query += " WHERE sequence = ?"
            params = (sequence,)
        query += " GROUP BY status"
        return {r["status"]: r["n"] for r in self.conn.execute(query, params)}

    # ---------------------------------------------------------------- messages

    def record_message(
        self,
        *,
        contact_id: int,
        step: int,
        mailbox_id: str,
        subject: str,
        body: str,
        status: str,
        msgid: str | None = None,
        in_reply_to: str | None = None,
        error: str | None = None,
        track_token: str | None = None,
        at: datetime | None = None,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO messages (contact_id, step, mailbox_id, subject, body,
                                  msgid, in_reply_to, status, sent_at, error, track_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (contact_id, step) DO UPDATE SET
                mailbox_id = excluded.mailbox_id,
                subject    = excluded.subject,
                body       = excluded.body,
                msgid      = COALESCE(excluded.msgid, messages.msgid),
                status     = excluded.status,
                sent_at    = COALESCE(excluded.sent_at, messages.sent_at),
                error      = excluded.error,
                attempts   = messages.attempts + 1
            """,
            (
                contact_id,
                step,
                mailbox_id,
                subject,
                body,
                msgid,
                in_reply_to,
                status,
                iso(at or utcnow()) if status == "sent" else None,
                error,
                track_token,
            ),
        )
        return int(cursor.lastrowid)

    def sent_between(self, mailbox_id: str, start: datetime, end: datetime) -> int:
        """Count sends in a half-open window. Callers pass local-day boundaries."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS n FROM messages
             WHERE mailbox_id = ? AND status = 'sent'
               AND sent_at >= ? AND sent_at < ?
            """,
            (mailbox_id, iso(start), iso(end)),
        ).fetchone()
        return int(row["n"])

    def attempts_for(self, contact_id: int, step: int) -> int:
        row = self.conn.execute(
            "SELECT attempts FROM messages WHERE contact_id = ? AND step = ?",
            (contact_id, step),
        ).fetchone()
        return int(row["attempts"]) if row else 0

    def contact_for_msgid(self, msgid: str) -> int | None:
        row = self.conn.execute(
            "SELECT contact_id FROM messages WHERE msgid = ?", (msgid,)
        ).fetchone()
        return int(row["contact_id"]) if row else None

    def all_sent_msgids(self) -> set[str]:
        return {
            r["msgid"]
            for r in self.conn.execute(
                "SELECT msgid FROM messages WHERE msgid IS NOT NULL AND status = 'sent'"
            )
        }

    # ----------------------------------------------------------- mailbox state

    def mailbox_state(self, mailbox_id: str) -> sqlite3.Row:
        self.conn.execute(
            "INSERT OR IGNORE INTO mailbox_state (mailbox_id) VALUES (?)", (mailbox_id,)
        )
        return self.conn.execute(
            "SELECT * FROM mailbox_state WHERE mailbox_id = ?", (mailbox_id,)
        ).fetchone()

    def mark_mailbox_sent(
        self,
        mailbox_id: str,
        next_allowed_at: datetime,
        today: date,
        at: datetime | None = None,
    ) -> None:
        state = self.mailbox_state(mailbox_id)
        first = state["first_send_date"] or today.isoformat()
        self.conn.execute(
            """
            UPDATE mailbox_state
               SET next_allowed_at = ?, last_sent_at = ?, first_send_date = ?
             WHERE mailbox_id = ?
            """,
            (iso(next_allowed_at), iso(at or utcnow()), first, mailbox_id),
        )

    def set_imap_uid(self, mailbox_id: str, uid: int) -> None:
        self.mailbox_state(mailbox_id)
        self.conn.execute(
            "UPDATE mailbox_state SET imap_last_uid = ? WHERE mailbox_id = ?",
            (uid, mailbox_id),
        )

    # ------------------------------------------------------ suppression/events

    def suppress(self, email: str, reason: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO suppression (email, reason, at) VALUES (?, ?, ?)",
            (email.strip().lower(), reason, iso(utcnow())),
        )

    def is_suppressed(self, email: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM suppression WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
            is not None
        )

    def load_suppression_file(self, path: Path) -> int:
        """Bulk-load a newline-delimited suppression list. Returns rows added."""
        if not path.exists():
            return 0
        added = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = line.strip()
            if entry and not entry.startswith("#"):
                self.suppress(entry, reason="file")
                added += 1
        return added

    def log_event(self, contact_id: int | None, event_type: str, detail: str = "") -> None:
        self.conn.execute(
            "INSERT INTO events (contact_id, type, at, detail) VALUES (?, ?, ?, ?)",
            (contact_id, event_type, iso(utcnow()), detail),
        )

    def record_open(self, token: str, user_agent: str = "", ip: str = "") -> None:
        self.conn.execute(
            "INSERT INTO opens (track_token, at, user_agent, ip) VALUES (?, ?, ?, ?)",
            (token, iso(utcnow()), user_agent, ip),
        )

    # ------------------------------------------------------------------- stats

    def stats(self) -> dict[str, Any]:
        def scalar(sql: str, params: Iterable = ()) -> int:
            return int(self.conn.execute(sql, tuple(params)).fetchone()[0])

        sent = scalar("SELECT COUNT(*) FROM messages WHERE status = 'sent'")
        unique_opened = scalar(
            "SELECT COUNT(DISTINCT track_token) FROM opens WHERE track_token IN "
            "(SELECT track_token FROM messages WHERE status = 'sent')"
        )
        return {
            "contacts": self.counts_by_status(),
            "sent": sent,
            "failed": scalar("SELECT COUNT(*) FROM messages WHERE status = 'failed'"),
            "replies": scalar("SELECT COUNT(*) FROM events WHERE type = 'replied'"),
            "bounces": scalar("SELECT COUNT(*) FROM events WHERE type = 'bounced'"),
            "unsubscribes": scalar("SELECT COUNT(*) FROM events WHERE type = 'unsubscribed'"),
            "opens": unique_opened,
            "per_mailbox_today": {
                r["mailbox_id"]: r["n"]
                for r in self.conn.execute(
                    """
                    SELECT mailbox_id, COUNT(*) AS n FROM messages
                     WHERE status = 'sent' AND substr(sent_at, 1, 10) = ?
                     GROUP BY mailbox_id
                    """,
                    (utcnow().date().isoformat(),),
                )
            },
        }
