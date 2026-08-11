"""Refusals the web app has to recognise, not just print.

A refusal has two audiences. The person reading it needs a sentence saying
what to do next - the routers already write those, and they stay exactly as
written. The screen showing it sometimes needs to do more than print that
sentence: "your profile is not complete enough" should open the modal that
links to the profile, and "they are already on your list" should offer the
person you already have rather than a red line under a form.

Matching on the message is how that gets done wrong. The sentence is the part
most likely to be reworded, and a reworded sentence silently turns the modal
back into red text with nobody noticing. So a refusal the UI treats specially
carries a stable code beside the message:

    {"detail": {"code": "profile_incomplete", "message": "Fill in ..."}}

Plain `HTTPException(status, "a sentence")` keeps working and still reaches
the user - the web client reads both shapes. Reach for `AppError` when the
code is load-bearing.
"""

from __future__ import annotations

from fastapi import HTTPException

# The codes. Named here rather than spelled inline at each raise, so the set
# the web app switches on is one readable list rather than a grep.
PROFILE_INCOMPLETE = "profile_incomplete"
OWN_ADDRESS = "own_address"
DUPLICATE_TARGET = "duplicate_target"
SEQUENCE_ENDED = "sequence_ended"
SUPPRESSED = "suppressed"
DEAD_ADDRESS = "dead_address"
GUARD_BLOCKED = "guard_blocked"
POOL_ACCESS_REQUIRED = "pool_access_required"
POOL_CONTACT_MISSING = "pool_contact_missing"
TARGET_NOT_FOUND = "target_not_found"
REPLY_NOT_FOUND = "reply_not_found"
NO_DRAFT = "no_draft"
MISSING_SUBJECT = "missing_subject"
SEND_BLOCKED = "send_blocked"
GMAIL_DISCONNECTED = "gmail_disconnected"
GMAIL_FAILED = "gmail_failed"
AI_FAILED = "ai_failed"


class AppError(HTTPException):
    """An HTTPException whose detail is `{code, message}` instead of a string."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code, {"code": code, "message": message})
        self.code = code
        self.message = message
