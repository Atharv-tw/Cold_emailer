"""IMAP polling: replies, bounces, auto-responders and unsubscribe requests.

A reply is the whole point of cold email, so detection has to be reliable.
We match on two signals:

* ``In-Reply-To`` / ``References`` containing a Message-ID we sent - exact.
* the sender address matching a contact - catches clients that drop threading
  headers, and replies sent from an alias.

Out-of-office autoresponders are explicitly *not* treated as replies. They
would otherwise silently kill a sequence for someone who is simply on leave.
"""

from __future__ import annotations

import email
import imaplib
import re
from dataclasses import dataclass
from datetime import timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr
from typing import Callable

from .config import Config, Mailbox
from .store import Store, utcnow

BOUNCE_SENDERS = ("mailer-daemon", "postmaster", "no-reply", "noreply")
BOUNCE_SUBJECTS = (
    "undeliverable", "delivery status notification", "returned mail",
    "delivery has failed", "mail delivery failed", "address not found",
)
AUTOREPLY_SUBJECTS = (
    "out of office", "automatic reply", "auto-reply", "autoreply",
    "away from my", "on annual leave", "on vacation", "maternity leave",
    "parental leave", "ooo:",
)
UNSUB_PHRASES = (
    "unsubscribe", "remove me", "take me off", "opt out", "opt-out",
    "stop emailing", "do not contact", "don't contact me", "not interested, remove",
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
AUTOREPLY_DEFER = timedelta(days=7)


@dataclass
class ReplyResult:
    mailbox_id: str
    scanned: int = 0
    replies: int = 0
    bounces: int = 0
    unsubscribes: int = 0
    autoreplies: int = 0
    error: str = ""


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001 - malformed headers are common in bounces
        return value


def _body_text(msg: Message, limit: int = 20000) -> str:
    chunks: list[str] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_type() in ("text/plain", "message/delivery-status", "text/rfc822-headers"):
            try:
                payload = part.get_payload(decode=True) or b""
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
            except Exception:  # noqa: BLE001
                continue
    return "\n".join(chunks)[:limit]


def _referenced_msgids(msg: Message) -> list[str]:
    raw = f"{msg.get('In-Reply-To', '')} {msg.get('References', '')}"
    return re.findall(r"<[^<>@\s]+@[^<>\s]+>", raw)


def _is_autoreply(msg: Message, subject: str) -> bool:
    if (msg.get("Auto-Submitted", "").lower().startswith("auto")
            or msg.get("X-Autoreply")
            or msg.get("X-Autorespond")
            or msg.get("Precedence", "").lower() in ("auto_reply", "bulk")):
        return True
    lowered = subject.lower()
    return any(marker in lowered for marker in AUTOREPLY_SUBJECTS)


def _is_bounce(from_addr: str, subject: str) -> bool:
    local = from_addr.split("@", 1)[0].lower()
    if any(marker in local for marker in BOUNCE_SENDERS):
        return True
    lowered = subject.lower()
    return any(marker in lowered for marker in BOUNCE_SUBJECTS)


def poll_mailbox(
    cfg: Config,
    store: Store,
    mailbox: Mailbox,
    *,
    baseline_only: bool = False,
    log: Callable[[str], None] = print,
) -> ReplyResult:
    """Scan one mailbox for new inbound mail since the last recorded UID."""
    result = ReplyResult(mailbox_id=mailbox.id)
    state = store.mailbox_state(mailbox.id)
    last_uid = int(state["imap_last_uid"] or 0)

    try:
        conn = imaplib.IMAP4_SSL(mailbox.imap_host, mailbox.imap_port)
    except Exception as exc:  # noqa: BLE001
        result.error = f"IMAP connect failed: {exc}"
        return result

    try:
        conn.login(mailbox.username, mailbox.password)
        conn.select("INBOX")

        status, data = conn.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        if status != "OK":
            result.error = f"IMAP search failed: {status}"
            return result

        uids = [int(u) for u in (data[0] or b"").split() if int(u) > last_uid]
        if not uids:
            return result

        # First run on an existing mailbox: record where we are and stop, so we
        # don't reprocess years of history.
        if last_uid == 0 or baseline_only:
            store.set_imap_uid(mailbox.id, max(uids))
            log(f"  {mailbox.id}: baseline set at UID {max(uids)} ({len(uids)} existing messages ignored)")
            return result

        our_msgids = store.all_sent_msgids()

        for uid in uids:
            status, payload = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            msg = email.message_from_bytes(payload[0][1])
            result.scanned += 1

            subject = _decode(msg.get("Subject"))
            from_addr = parseaddr(_decode(msg.get("From")))[1].lower()

            contact = None
            for msgid in _referenced_msgids(msg):
                if msgid in our_msgids:
                    contact_id = store.contact_for_msgid(msgid)
                    if contact_id:
                        contact = store.get_contact(contact_id)
                        break

            if _is_bounce(from_addr, subject):
                body = _body_text(msg)
                candidates = {a.lower() for a in EMAIL_RE.findall(body)}
                if contact:
                    candidates.add(contact["email"])
                for address in candidates:
                    hit = store.find_contact_by_email(address)
                    if hit and hit["status"] not in ("bounced", "unsubscribed"):
                        store.set_contact_status(int(hit["id"]), "bounced", subject[:200])
                        store.suppress(address, reason="bounce")
                        result.bounces += 1
                        break
                continue

            if contact is None:
                contact = store.find_contact_by_email(from_addr)
            if contact is None:
                continue

            contact_id = int(contact["id"])
            body_lower = _body_text(msg, 4000).lower()

            if any(phrase in body_lower or phrase in subject.lower() for phrase in UNSUB_PHRASES):
                store.set_contact_status(contact_id, "unsubscribed", "requested by reply")
                store.suppress(contact["email"], reason="reply opt-out")
                result.unsubscribes += 1
                continue

            if _is_autoreply(msg, subject):
                # Not a real reply. Pause this contact for a week and resume.
                store.log_event(contact_id, "auto_reply", subject[:200])
                if contact["status"] == "active" and contact["next_due_at"]:
                    store.set_next_due(contact_id, utcnow() + AUTOREPLY_DEFER)
                result.autoreplies += 1
                continue

            if contact["status"] == "active":
                store.set_contact_status(contact_id, "replied", subject[:200])
                result.replies += 1

        store.set_imap_uid(mailbox.id, max(uids))

    except imaplib.IMAP4.error as exc:
        result.error = f"IMAP error: {exc}"
    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001
            pass

    return result


def poll_all(
    cfg: Config,
    store: Store,
    *,
    baseline_only: bool = False,
    log: Callable[[str], None] = print,
) -> list[ReplyResult]:
    return [
        poll_mailbox(cfg, store, mailbox, baseline_only=baseline_only, log=log)
        for mailbox in cfg.active_mailboxes
    ]
