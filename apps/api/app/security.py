"""Our own session tokens.

Google's ID token proves who someone is at the moment they sign in. It is not
a session: it expires on Google's schedule, carries claims we do not need on
every request, and re-verifying it per request means a network round trip. So
we verify it once and issue our own short-lived token against it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"
ISSUER = "outreach-api"
COOKIE_NAME = "outreach_session"


class SessionError(Exception):
    pass


def issue_session(user_id: uuid.UUID, secret: str, ttl_minutes: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ttl_minutes)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "iss": ISSUER,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        },
        secret,
        algorithm=ALGORITHM,
    )
    return token, expires


def read_session(token: str, secret: str) -> uuid.UUID:
    try:
        claims = jwt.decode(token, secret, algorithms=[ALGORITHM], issuer=ISSUER)
    except jwt.ExpiredSignatureError as exc:
        raise SessionError("session expired") from exc
    except jwt.InvalidTokenError as exc:
        raise SessionError("invalid session") from exc
    try:
        return uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise SessionError("session has no usable subject") from exc
