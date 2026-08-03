"""Verifying who Google says someone is.

The web app runs the OAuth dance and hands us the resulting ID token. We do
not take its word for the identity inside: the token is verified against
Google's published signing keys, with the audience pinned to our own client
id. Skipping that check would let anyone with *any* Google ID token - from any
app - sign in as anyone here.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# Scopes the product needs. `gmail.readonly` is what makes reply tracking
# possible; without it we would be sending into a void and guessing.
REQUIRED_SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
)


class GoogleAuthError(Exception):
    pass


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str
    picture: str
    email_verified: bool


@lru_cache
def _jwk_client() -> PyJWKClient:
    # Caches keys in-process and refetches on rotation.
    return PyJWKClient(CERTS_URL, cache_keys=True)


def verify_id_token(id_token: str, client_id: str) -> GoogleIdentity:
    if not client_id:
        raise GoogleAuthError("GOOGLE_CLIENT_ID is not configured")
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=list(ISSUERS),
        )
    except jwt.PyJWTError as exc:
        raise GoogleAuthError(f"could not verify Google ID token: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - key fetch failures land here
        raise GoogleAuthError(f"could not reach Google's signing keys: {exc}") from exc

    if not claims.get("email"):
        raise GoogleAuthError("Google ID token carries no email address")

    # An unverified address would let someone claim a mailbox they do not own.
    if not claims.get("email_verified", False):
        raise GoogleAuthError("this Google account's email address is not verified")

    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=str(claims["email"]).lower(),
        name=str(claims.get("name", "")),
        picture=str(claims.get("picture", "")),
        email_verified=True,
    )


def missing_scopes(granted: list[str] | None) -> list[str]:
    """Which required scopes the user did not grant.

    Google's consent screen lets people untick individual scopes. Dropping
    `gmail.readonly` in particular leaves the app able to send but blind to
    replies, which is the one state this product must never operate in
    silently.
    """
    have = set(granted or [])
    return [scope for scope in REQUIRED_SCOPES if scope not in have]
