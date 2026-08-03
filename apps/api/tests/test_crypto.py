"""Envelope encryption and session tokens.

A refresh token is a long-lived key to somebody's mailbox, so the properties
tested here are not incidental: ciphertext must not be reversible without the
master key, must not be movable between users, and must not survive tampering.
"""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crypto import (  # noqa: E402
    DecryptionError, Envelope, Secret, decrypt, encrypt,
)
from app.security import SessionError, issue_session, read_session  # noqa: E402

MASTER = os.urandom(32)
OTHER_MASTER = os.urandom(32)


class TestEnvelopeEncryption(unittest.TestCase):
    def test_round_trip(self):
        blob = encrypt("1//refresh-token", MASTER)
        self.assertEqual(decrypt(blob, MASTER), "1//refresh-token")

    def test_plaintext_does_not_appear_in_the_ciphertext(self):
        blob = encrypt("1//refresh-token", MASTER)
        self.assertNotIn("refresh-token", blob)

    def test_every_record_gets_its_own_data_key(self):
        # Same plaintext, same master key, different ciphertext - otherwise the
        # table leaks which users share a value.
        first = encrypt("same", MASTER)
        second = encrypt("same", MASTER)
        self.assertNotEqual(first, second)
        self.assertNotEqual(Envelope.parse(first).wrapped_key, Envelope.parse(second).wrapped_key)

    def test_wrong_master_key_fails_closed(self):
        blob = encrypt("secret", MASTER)
        with self.assertRaises(DecryptionError):
            decrypt(blob, OTHER_MASTER)

    def test_tampering_is_detected(self):
        envelope = Envelope.parse(encrypt("secret", MASTER))
        mangled = Envelope(
            envelope.wrapped_key,
            envelope.nonce,
            envelope.ciphertext[:-1] + bytes([envelope.ciphertext[-1] ^ 0x01]),
        )
        with self.assertRaises(DecryptionError):
            decrypt(mangled.serialise(), MASTER)

    def test_ciphertext_is_bound_to_its_user(self):
        # A row lifted from one user and pasted onto another must not decrypt.
        alice, bob = str(uuid.uuid4()).encode(), str(uuid.uuid4()).encode()
        blob = encrypt("alice's token", MASTER, aad=alice)
        self.assertEqual(decrypt(blob, MASTER, aad=alice), "alice's token")
        with self.assertRaises(DecryptionError):
            decrypt(blob, MASTER, aad=bob)

    def test_malformed_blob_is_rejected(self):
        for bad in ("", "nonsense", "v1.only.two"):
            with self.assertRaises(DecryptionError):
                decrypt(bad, MASTER)

    def test_unknown_scheme_is_rejected(self):
        blob = encrypt("secret", MASTER)
        with self.assertRaises(DecryptionError):
            decrypt("v9" + blob[2:], MASTER)


class TestSecret(unittest.TestCase):
    def test_value_is_not_reachable_by_accident(self):
        secret = Secret("1//refresh-token")
        self.assertNotIn("refresh-token", repr(secret))
        self.assertNotIn("refresh-token", str(secret))
        self.assertNotIn("refresh-token", f"{secret}")
        self.assertNotIn("refresh-token", f"{secret!r}")
        self.assertEqual(secret.reveal(), "1//refresh-token")

    def test_truthiness_without_revealing(self):
        self.assertTrue(Secret("x"))
        self.assertFalse(Secret(""))


class TestSessionTokens(unittest.TestCase):
    def setUp(self):
        # At least 32 bytes, matching what Settings enforces at startup.
        self.secret = "test-session-secret-padded-to-32-bytes-or-more"
        self.user_id = uuid.uuid4()

    def test_round_trip(self):
        token, _ = issue_session(self.user_id, self.secret, 60)
        self.assertEqual(read_session(token, self.secret), self.user_id)

    def test_another_secret_cannot_forge_a_session(self):
        token, _ = issue_session(self.user_id, self.secret, 60)
        with self.assertRaises(SessionError):
            read_session(token, "a-different-secret-also-32-bytes-long-here")

    def test_expired_session_is_refused(self):
        token, expires = issue_session(self.user_id, self.secret, -1)
        self.assertLess(expires.timestamp(), (expires + timedelta(minutes=2)).timestamp())
        with self.assertRaises(SessionError):
            read_session(token, self.secret)

    def test_garbage_is_refused(self):
        with self.assertRaises(SessionError):
            read_session("not.a.jwt", self.secret)


if __name__ == "__main__":
    unittest.main(verbosity=2)
