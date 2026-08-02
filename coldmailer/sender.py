"""SMTP delivery: message construction, threading headers, transport."""

from __future__ import annotations

import html
import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from urllib.parse import quote

from .config import Config, Mailbox


class SendError(Exception):
    """Raised for a delivery failure we could not classify as permanent."""


class PermanentSendError(SendError):
    """Recipient rejected outright - do not retry, suppress the address."""


@dataclass
class Outgoing:
    to_email: str
    subject: str
    body: str
    in_reply_to: str | None = None
    references: str = ""
    track_token: str | None = None
    unsub_token: str = ""


def _pixel_html(body: str, base_url: str, token: str) -> str:
    paragraphs = "".join(
        f"<p>{html.escape(chunk).replace(chr(10), '<br>')}</p>"
        for chunk in body.split("\n\n")
        if chunk.strip()
    )
    pixel = f'<img src="{base_url}/o/{quote(token)}.png" width="1" height="1" alt="" style="display:none">'
    return f'<div style="font-family:-apple-system,Segoe UI,sans-serif;font-size:14px">{paragraphs}{pixel}</div>'


def build_message(cfg: Config, mailbox: Mailbox, out: Outgoing) -> EmailMessage:
    """Assemble the MIME message, including RFC 5322 threading headers."""
    msg = EmailMessage()
    msg["From"] = formataddr((mailbox.from_name, mailbox.email))
    msg["To"] = out.to_email
    msg["Subject"] = out.subject
    msg["Date"] = formatdate(localtime=True)

    domain = mailbox.email.split("@", 1)[-1]
    msg["Message-ID"] = make_msgid(domain=domain)

    if mailbox.reply_to:
        msg["Reply-To"] = mailbox.reply_to

    # Threading: follow-ups must reference the whole chain so Gmail and
    # Outlook collapse them into the original conversation.
    if out.in_reply_to:
        msg["In-Reply-To"] = out.in_reply_to
        references = f"{out.references} {out.in_reply_to}".strip()
        msg["References"] = references

    # Unsubscribe headers. Gmail requires these above trivial volume.
    unsub_targets = [
        f"<mailto:{cfg.identity.unsubscribe_mailto}?subject=unsubscribe>"
    ]
    if cfg.tracking.base_url and out.unsub_token:
        url = f"{cfg.tracking.base_url}/u/{quote(out.unsub_token)}"
        unsub_targets.insert(0, f"<{url}>")
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["List-Unsubscribe"] = ", ".join(unsub_targets)

    # Plain text is the default on purpose: it looks like a person typed it,
    # and it consistently outperforms HTML for cold outreach.
    msg.set_content(out.body)

    if cfg.tracking.open_tracking and out.track_token:
        msg.add_alternative(
            _pixel_html(out.body, cfg.tracking.base_url, out.track_token),
            subtype="html",
        )

    return msg


def _connect(mailbox: Mailbox, timeout: int = 30) -> smtplib.SMTP:
    context = ssl.create_default_context()
    if mailbox.smtp_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            mailbox.smtp_host, mailbox.smtp_port, timeout=timeout, context=context
        )
    else:
        server = smtplib.SMTP(mailbox.smtp_host, mailbox.smtp_port, timeout=timeout)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
    server.login(mailbox.username, mailbox.password)
    return server


def send(cfg: Config, mailbox: Mailbox, out: Outgoing) -> str:
    """Deliver one message. Returns the Message-ID on success."""
    msg = build_message(cfg, mailbox, out)
    server = None
    try:
        server = _connect(mailbox)
        server.send_message(msg)
    except smtplib.SMTPRecipientsRefused as exc:
        raise PermanentSendError(f"recipient refused: {exc.recipients}") from exc
    except smtplib.SMTPResponseException as exc:
        detail = f"{exc.smtp_code} {exc.smtp_error!r}"
        if 500 <= exc.smtp_code < 600:
            raise PermanentSendError(detail) from exc
        raise SendError(detail) from exc
    except (smtplib.SMTPException, socket.error, ssl.SSLError, OSError) as exc:
        raise SendError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:  # noqa: BLE001 - a failed QUIT is not interesting
                pass
    return msg["Message-ID"]


def test_connection(mailbox: Mailbox) -> tuple[bool, str]:
    """Verify SMTP credentials without sending anything."""
    try:
        server = _connect(mailbox, timeout=15)
        server.quit()
        return True, "SMTP login OK"
    except smtplib.SMTPAuthenticationError as exc:
        return False, (
            f"authentication failed ({exc.smtp_code}). For Google Workspace this "
            f"usually means 2FA is off or you used your account password instead "
            f"of a 16-character app password."
        )
    except Exception as exc:  # noqa: BLE001 - surface anything to the operator
        return False, f"{type(exc).__name__}: {exc}"
