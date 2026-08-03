"""Message construction and RFC 5322 threading headers.

Transport is no longer SMTP - the API sends through Gmail - but what goes on
the wire is still a MIME message, and the headers that make a follow-up land
inside the original conversation rather than as a fresh email are the same.

One deliberate omission: ``List-Unsubscribe``. It is required of bulk senders
and correct for marketing mail, but this platform sends personal mail only.
On a one-to-one note the header marks an otherwise normal email as a mailing
list blast, which costs replies for no benefit. Opt-out is still honoured
permanently - see :mod:`outreach_core.classify` - it just isn't advertised in
a header, because a person writing to one other person doesn't have a list.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate


@dataclass(frozen=True)
class SenderIdentity:
    """Who the mail is from. One connected Google account."""

    email: str
    from_name: str
    reply_to: str | None = None


@dataclass(frozen=True)
class Outgoing:
    to_email: str
    subject: str
    body: str
    # Message-ID of the previous message in this thread, for follow-ups.
    in_reply_to: str | None = None
    # Accumulated chain, oldest first. Gmail and Outlook both need the whole
    # chain, not just the immediate parent, to collapse the conversation.
    references: str = ""


def build_message(
    sender: SenderIdentity,
    out: Outgoing,
    *,
    message_id: str | None = None,
) -> EmailMessage:
    """Assemble the MIME message.

    ``message_id`` is normally left unset. Gmail assigns the real Message-ID
    when it accepts the message, and that assigned value - read back from the
    send response - is what must be stored and used as the ``In-Reply-To`` of
    the next touch. Setting one here and trusting it would break threading the
    moment Gmail rewrote it.
    """
    msg = EmailMessage()
    msg["From"] = formataddr((sender.from_name, sender.email))
    msg["To"] = out.to_email
    msg["Subject"] = out.subject
    msg["Date"] = formatdate(localtime=True)

    if message_id:
        msg["Message-ID"] = message_id
    if sender.reply_to:
        msg["Reply-To"] = sender.reply_to

    if out.in_reply_to:
        msg["In-Reply-To"] = out.in_reply_to
        msg["References"] = f"{out.references} {out.in_reply_to}".strip()

    # Plain text on purpose: it looks like a person typed it, and it
    # consistently outperforms HTML for cold outreach.
    msg.set_content(out.body)
    return msg


def extend_references(references: str, message_id: str) -> str:
    """Append a Message-ID to a References chain, preserving order."""
    return f"{references or ''} {message_id}".strip()


def to_gmail_raw(msg: EmailMessage) -> str:
    """Encode for ``users.messages.send``: base64url, no padding issues."""
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
