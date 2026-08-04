"""ID token verification.

No network: the signing key is generated here and `_jwk_client` is replaced,
so these exercise the claim checks rather than Google's key endpoint.
"""

from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest import mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.google_oauth import (
    CLOCK_SKEW,
    REQUIRED_SCOPES,
    GoogleAuthError,
    missing_scopes,
    verify_id_token,
)

CLIENT_ID = "client.apps.googleusercontent.com"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(**overrides: object) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "someone@example.com",
        "email_verified": True,
        "name": "Someone",
        "picture": "https://example.com/a.png",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, _KEY, algorithm="RS256")


class VerifyIdTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch(
            "app.services.google_oauth._jwk_client",
            return_value=SimpleNamespace(
                get_signing_key_from_jwt=lambda _: SimpleNamespace(key=_KEY.public_key())
            ),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_accepts_a_well_formed_token(self) -> None:
        identity = verify_id_token(token(), CLIENT_ID)
        self.assertEqual(identity.sub, "1234567890")
        self.assertEqual(identity.email, "someone@example.com")

    def test_email_is_lowercased(self) -> None:
        identity = verify_id_token(token(email="Someone@Example.COM"), CLIENT_ID)
        self.assertEqual(identity.email, "someone@example.com")

    def test_tolerates_a_slightly_slow_clock(self) -> None:
        """The failure this exists for: `iat` ahead of us on an unsynced host.

        Google stamps `iat` from its own clock. A server running a few seconds
        behind sees that as a token from the future and rejects every sign-in,
        which is a total outage with no bad input anywhere in it.
        """
        skew = int(CLOCK_SKEW.total_seconds()) - 1
        identity = verify_id_token(token(iat=int(time.time()) + skew), CLIENT_ID)
        self.assertEqual(identity.sub, "1234567890")

    def test_rejects_a_clock_that_is_wrong_rather_than_skewed(self) -> None:
        far = int(time.time()) + 3600
        with self.assertRaises(GoogleAuthError):
            verify_id_token(token(iat=far, exp=far + 3600), CLIENT_ID)

    def test_rejects_an_expired_token(self) -> None:
        past = int(time.time()) - 7200
        with self.assertRaises(GoogleAuthError):
            verify_id_token(token(iat=past, exp=past + 3600), CLIENT_ID)

    def test_rejects_another_apps_token(self) -> None:
        with self.assertRaises(GoogleAuthError):
            verify_id_token(token(aud="someone-elses-client-id"), CLIENT_ID)

    def test_rejects_an_unexpected_issuer(self) -> None:
        with self.assertRaises(GoogleAuthError):
            verify_id_token(token(iss="https://evil.example.com"), CLIENT_ID)

    def test_rejects_an_unverified_email(self) -> None:
        with self.assertRaises(GoogleAuthError):
            verify_id_token(token(email_verified=False), CLIENT_ID)

    def test_rejects_when_no_client_id_is_configured(self) -> None:
        with self.assertRaises(GoogleAuthError):
            verify_id_token(token(), "")


class MissingScopesTests(unittest.TestCase):
    # Verbatim from Google's token endpoint for a consent where every box was
    # left ticked. Note `userinfo.email` and `userinfo.profile`: the grant does
    # not come back under the alias it was asked for.
    FULLY_GRANTED = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    def test_nothing_missing_when_everything_was_granted(self) -> None:
        self.assertEqual(missing_scopes(self.FULLY_GRANTED), [])

    def test_accepts_the_aliases_too(self) -> None:
        """In case Google ever echoes back what it was asked for."""
        granted = [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
        ]
        self.assertEqual(missing_scopes(granted), [])

    def test_reports_readonly_when_it_was_unticked(self) -> None:
        granted = [s for s in self.FULLY_GRANTED if not s.endswith("gmail.readonly")]
        self.assertEqual(
            missing_scopes(granted),
            ["https://www.googleapis.com/auth/gmail.readonly"],
        )

    def test_reports_an_identity_scope_by_the_name_we_asked_for(self) -> None:
        granted = [s for s in self.FULLY_GRANTED if not s.endswith("userinfo.email")]
        self.assertEqual(missing_scopes(granted), ["email"])

    def test_nothing_granted(self) -> None:
        self.assertEqual(len(missing_scopes([])), len(REQUIRED_SCOPES))
        self.assertEqual(len(missing_scopes(None)), len(REQUIRED_SCOPES))


if __name__ == "__main__":
    unittest.main()
