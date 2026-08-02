"""Configuration loading and validation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class ConfigError(Exception):
    """Raised when the config file is missing something we need."""


@dataclass
class Mailbox:
    id: str
    email: str
    from_name: str
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    username: str
    password: str
    daily_cap: int
    reply_to: str | None = None
    first_send_date: date | None = None
    enabled: bool = True
    smtp_ssl: bool = False

    def __repr__(self) -> str:  # never leak the password into logs
        return f"<Mailbox {self.id} {self.email} cap={self.daily_cap}>"


@dataclass
class Warmup:
    enabled: bool = True
    start_cap: int = 10
    increment_per_day: int = 3
    max_cap: int = 40

    def cap_for(self, mailbox: Mailbox, today: date) -> int:
        """Daily cap for a mailbox, ramped up from its first send date."""
        hard_cap = mailbox.daily_cap
        if not self.enabled or mailbox.first_send_date is None:
            return hard_cap if not self.enabled else min(self.start_cap, hard_cap)
        days_active = (today - mailbox.first_send_date).days
        ramped = self.start_cap + self.increment_per_day * max(0, days_active)
        return max(1, min(ramped, self.max_cap, hard_cap))


@dataclass
class Sending:
    timezone: str = "UTC"
    window_start: time = time(9, 0)
    window_end: time = time(17, 0)
    days: list[str] = field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])
    min_gap_seconds: int = 180
    max_gap_seconds: int = 900
    max_per_tick: int = 5

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def is_sending_time(self, moment: datetime) -> bool:
        """True when `moment` (any tz-aware datetime) falls in the send window."""
        local = moment.astimezone(self.tz)
        if DAY_NAMES[local.weekday()] not in self.days:
            return False
        return self.window_start <= local.time() <= self.window_end


@dataclass
class Identity:
    from_name: str
    company: str
    physical_address: str
    unsubscribe_mailto: str
    unsubscribe_line: str = (
        "Not relevant? Reply 'unsubscribe' and I won't contact you again."
    )

    # How much compliance boilerplate to append.
    #
    #   full     postal address + opt-out line. Required by CAN-SPAM for
    #            commercial marketing mail. Also unmistakably signals "mass
    #            mailing" to the reader.
    #   minimal  one polite opt-out line, no address.
    #   none     nothing. Correct for genuine person-to-person outreach -
    #            job applications, research enquiries - where the message is
    #            not advertising a product and a footer would only make a
    #            personal note look automated.
    footer: str = "full"

    # Merge fields available to every template without repeating them in the
    # CSV: your name, resume link, availability, and so on. A column in the
    # contact file with the same name wins.
    vars: dict[str, str] = field(default_factory=dict)

    @property
    def is_bulk(self) -> bool:
        """True when this is marketing mail that needs unsubscribe machinery."""
        return self.footer != "none"


@dataclass
class Tracking:
    open_tracking: bool = False
    base_url: str = ""


@dataclass
class Config:
    identity: Identity
    sending: Sending
    warmup: Warmup
    tracking: Tracking
    mailboxes: list[Mailbox]
    db_path: Path
    sequences_dir: Path
    suppression_file: Path
    source_path: Path

    def mailbox(self, mailbox_id: str) -> Mailbox | None:
        return next((m for m in self.mailboxes if m.id == mailbox_id), None)

    @property
    def active_mailboxes(self) -> list[Mailbox]:
        return [m for m in self.mailboxes if m.enabled]


def _parse_time(value: Any, label: str) -> time:
    if isinstance(value, time):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,2}:\d{2}", value):
        raise ConfigError(f"{label} must look like '09:30', got {value!r}")
    hour, minute = (int(part) for part in value.split(":"))
    if hour > 23 or minute > 59:
        raise ConfigError(f"{label} is not a real time: {value!r}")
    return time(hour, minute)


def _parse_date(value: Any, label: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigError(f"{label} must be YYYY-MM-DD, got {value!r}") from exc


def _resolve_password(raw: dict[str, Any], mailbox_id: str) -> str:
    """Passwords come from the environment. Never from the config file."""
    env_name = raw.get("password_env")
    if not env_name:
        raise ConfigError(
            f"mailbox '{mailbox_id}' needs a password_env pointing at an "
            f"environment variable (e.g. password_env: MB1_PASSWORD). "
            f"Passwords are deliberately not read from the config file."
        )
    password = os.environ.get(env_name, "")
    if not password:
        raise ConfigError(
            f"mailbox '{mailbox_id}': environment variable {env_name} is empty "
            f"or unset. Set it before running, e.g.  export {env_name}='...'"
        )
    return password


def _build_mailbox(
    raw: dict[str, Any],
    index: int,
    default_from: str,
    default_cap: int,
    *,
    require_password: bool = True,
) -> Mailbox:
    mailbox_id = str(raw.get("id") or f"mb{index + 1}")
    email = raw.get("email")
    if not email:
        raise ConfigError(f"mailbox '{mailbox_id}' is missing 'email'")

    if raw.get("password"):
        raise ConfigError(
            f"mailbox '{mailbox_id}' has a literal 'password' in the config. "
            f"Use password_env pointing at an environment variable instead."
        )

    smtp_port = int(raw.get("smtp_port", 587))
    return Mailbox(
        id=mailbox_id,
        email=email,
        from_name=raw.get("from_name") or default_from,
        smtp_host=raw.get("smtp_host", "smtp.gmail.com"),
        smtp_port=smtp_port,
        imap_host=raw.get("imap_host", "imap.gmail.com"),
        imap_port=int(raw.get("imap_port", 993)),
        username=raw.get("username") or email,
        password=_resolve_password(raw, mailbox_id) if require_password else "",
        daily_cap=int(raw.get("daily_cap", default_cap)),
        reply_to=raw.get("reply_to"),
        first_send_date=_parse_date(raw.get("first_send_date"), f"mailbox '{mailbox_id}' first_send_date"),
        enabled=bool(raw.get("enabled", True)),
        smtp_ssl=bool(raw.get("smtp_ssl", smtp_port == 465)),
    )


def load_config(path: str | Path, *, require_passwords: bool = True) -> Config:
    """Read and validate the YAML config."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"No config at {path}. Copy config.example.yaml to config.yaml and edit it."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    identity_raw = raw.get("identity") or {}

    footer_mode = str(identity_raw.get("footer", "full")).lower()
    if footer_mode not in ("full", "minimal", "none"):
        raise ConfigError(f"identity.footer must be full, minimal or none - got {footer_mode!r}")

    required = ["from_name"]
    if footer_mode == "full":
        required += ["physical_address", "unsubscribe_mailto"]
    elif footer_mode == "minimal":
        required += ["unsubscribe_mailto"]

    missing = [k for k in required if not identity_raw.get(k)]
    if missing:
        detail = ""
        if footer_mode == "full":
            detail = (
                " A physical postal address and a working unsubscribe route are "
                "required by CAN-SPAM for commercial marketing email. If this is "
                "person-to-person outreach rather than marketing - a job "
                "application, a research enquiry - set identity.footer: none."
            )
        raise ConfigError(
            "identity is missing required field(s): " + ", ".join(missing) + "." + detail
        )

    identity_vars = identity_raw.get("vars") or {}
    if not isinstance(identity_vars, dict):
        raise ConfigError("identity.vars must be a mapping of name: value")

    identity = Identity(
        from_name=identity_raw["from_name"],
        company=identity_raw.get("company", ""),
        physical_address=identity_raw.get("physical_address", ""),
        unsubscribe_mailto=identity_raw.get("unsubscribe_mailto", ""),
        unsubscribe_line=identity_raw.get("unsubscribe_line", Identity.unsubscribe_line),
        footer=footer_mode,
        vars={str(k): str(v) for k, v in identity_vars.items()},
    )

    sending_raw = raw.get("sending") or {}
    try:
        tz_name = sending_raw.get("timezone", "UTC")
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Unknown timezone {tz_name!r}") from exc

    days = [str(d).lower()[:3] for d in sending_raw.get("days", ["mon", "tue", "wed", "thu", "fri"])]
    bad_days = [d for d in days if d not in DAY_NAMES]
    if bad_days:
        raise ConfigError(f"sending.days has unknown day(s): {bad_days}")

    sending = Sending(
        timezone=tz_name,
        window_start=_parse_time(sending_raw.get("window_start", "09:00"), "sending.window_start"),
        window_end=_parse_time(sending_raw.get("window_end", "17:00"), "sending.window_end"),
        days=days,
        min_gap_seconds=int(sending_raw.get("min_gap_seconds", 180)),
        max_gap_seconds=int(sending_raw.get("max_gap_seconds", 900)),
        max_per_tick=int(sending_raw.get("max_per_tick", 5)),
    )
    if sending.window_start >= sending.window_end:
        raise ConfigError("sending.window_start must be earlier than sending.window_end")
    if sending.min_gap_seconds > sending.max_gap_seconds:
        raise ConfigError("sending.min_gap_seconds cannot exceed max_gap_seconds")

    warmup_raw = raw.get("warmup") or {}
    warmup = Warmup(
        enabled=bool(warmup_raw.get("enabled", True)),
        start_cap=int(warmup_raw.get("start_cap", 10)),
        increment_per_day=int(warmup_raw.get("increment_per_day", 3)),
        max_cap=int(warmup_raw.get("max_cap", 40)),
    )

    tracking_raw = raw.get("tracking") or {}
    tracking = Tracking(
        open_tracking=bool(tracking_raw.get("open_tracking", False)),
        base_url=str(tracking_raw.get("base_url", "")).rstrip("/"),
    )
    if tracking.open_tracking and not tracking.base_url:
        raise ConfigError("tracking.open_tracking is on but tracking.base_url is empty")

    mailboxes_raw = raw.get("mailboxes") or []
    if not mailboxes_raw:
        raise ConfigError("config has no mailboxes")

    mailboxes: list[Mailbox] = [
        _build_mailbox(
            mb_raw, index, identity.from_name, warmup.max_cap,
            require_password=require_passwords,
        )
        for index, mb_raw in enumerate(mailboxes_raw)
    ]

    ids = [m.id for m in mailboxes]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ConfigError(f"duplicate mailbox id(s): {sorted(duplicates)}")

    paths_raw = raw.get("paths") or {}
    base = path.parent
    return Config(
        identity=identity,
        sending=sending,
        warmup=warmup,
        tracking=tracking,
        mailboxes=mailboxes,
        db_path=base / paths_raw.get("db", "coldmailer.db"),
        sequences_dir=base / paths_raw.get("sequences", "sequences"),
        suppression_file=base / paths_raw.get("suppression", "suppression.txt"),
        source_path=path,
    )
