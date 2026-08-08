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
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate

# Which profile link may appear in the signature, in order of preference. One
# only, and the first match wins. The body is already allowed a URL, and every
# additional link in a one-to-one email is another thing a filter counts and
# another place for the reader's attention to go instead of the reply.
#
# The order is what each link proves about a stranger, best first: a portfolio
# is curated and shows finished work, a LinkedIn is the conventional fallback,
# a GitHub is raw but real, and a resume is the last resort because it asks the
# reader to download something. `other` is deliberately absent - an unlabelled
# link is not worth the one slot.
SIGNATURE_LINK_KEYS = (
    ("portfolio", "Portfolio"),
    ("linkedin", "LinkedIn"),
    ("github", "GitHub"),
    ("resume", "Resume"),
)


def signature(name: str, links: Mapping[str, str]) -> str:
    """The sender's own block, appended after the body at send time.

    Deliberately not something the model writes. The generation prompt allows
    exactly one URL in the body so the email argues for itself instead of
    reading as a link dump - if the signature were part of what was generated,
    the model would spend that single allowance on a profile page.

    No "--" delimiter: it is the RFC 3676 convention, but Gmail collapses what
    follows it behind an ellipsis, which hides the link this exists to show.

    Returns "" when there is nothing to say, so a profile with no name and no
    portfolio does not append a bare separator to every email.
    """
    lines = [line for line in [name.strip()] if line]

    # Keys are whatever the user typed on their profile, so match on case-folded
    # names rather than requiring them to have written "portfolio" exactly.
    by_key = {str(k).strip().lower(): v for k, v in (links or {}).items()}
    for key, label in SIGNATURE_LINK_KEYS:
        url = str(by_key.get(key) or "").strip()
        if url:
            lines.append(f"{label}: {url}")
            break

    return "\n\n" + "\n".join(lines) if lines else ""


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
