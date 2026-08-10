"""Provider-agnostic deliverability logic.

This package is the part of the old single-user CLI that was worth keeping:
when a message may be sent, how many may go out, how a thread is assembled,
and what an inbound message actually means. None of it knows about Gmail,
Postgres, HTTP, or who the user is - it takes values and returns values.

Deliberately stdlib-only. The regression suite that guards it must be runnable
without installing anything, because it is the safety net for the rewrite.
"""

from .classify import (
    AUTOREPLY_DEFER,
    SOFT_BOUNCE_DEFER,
    Classification,
    Inbound,
    Verdict,
    classify,
    dsn_status,
    is_autoreply,
    is_bounce,
    is_permanent_bounce,
    is_transient_bounce,
)
from .limits import (
    MAX_CYCLES,
    MAX_TOUCHES,
    MIN_BUSINESS_DAYS_BETWEEN_TOUCHES,
    RESET_AFTER,
    RecipientGuard,
    TouchDecision,
    WarmupPolicy,
    may_schedule_touch,
    recipient_key,
    starts_new_cycle,
)
from .mime import Outgoing, SenderIdentity, build_message, to_gmail_raw
from .scheduling import (
    DAY_NAMES,
    SendingWindow,
    next_sending_day,
    random_time_in_window,
    schedule_step,
)
from .templating import (
    Rendered,
    TemplateError,
    expand_spintax,
    lint,
    render,
    render_draft,
    template_fields,
)

__all__ = [
    "AUTOREPLY_DEFER",
    "SOFT_BOUNCE_DEFER",
    "dsn_status",
    "is_permanent_bounce",
    "is_transient_bounce",
    "DAY_NAMES",
    "MAX_TOUCHES",
    "MAX_CYCLES",
    "RESET_AFTER",
    "starts_new_cycle",
    "MIN_BUSINESS_DAYS_BETWEEN_TOUCHES",
    "Classification",
    "Inbound",
    "Outgoing",
    "RecipientGuard",
    "Rendered",
    "SenderIdentity",
    "SendingWindow",
    "TemplateError",
    "TouchDecision",
    "Verdict",
    "WarmupPolicy",
    "build_message",
    "classify",
    "expand_spintax",
    "is_autoreply",
    "is_bounce",
    "lint",
    "may_schedule_touch",
    "next_sending_day",
    "random_time_in_window",
    "recipient_key",
    "render",
    "render_draft",
    "schedule_step",
    "template_fields",
    "to_gmail_raw",
]
