"""Envelope encryption for the few secrets that must live in the database.

Google refresh tokens are the reason this exists. A refresh token is a
long-lived key to somebody's mailbox: it can send mail as them and read their
inbox until they explicitly revoke it. Storing that in a plain column means a
single database leak hands over every connected mailbox.

Envelope encryption, per record:

    data key      random 32 bytes, used once, for exactly one record
    record        AES-256-GCM under the data key
    wrapped key   the data key, AES-256-GCM under the master key
    master key    from the environment, never in the database

Only the wrapped key and the ciphertext are stored, so rotating the master key
means rewrapping data keys rather than re-encrypting every record - and a
compromised database without the master key yields nothing. Moving to KMS
later replaces `_wrap`/`_unwrap` and nothing else.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEME = "v1"
NONCE_BYTES = 12
KEY_BYTES = 32


class DecryptionError(Exception):
    """Ciphertext could not be authenticated - wrong key, or tampering."""


@dataclass(frozen=True)
class Envelope:
    wrapped_key: bytes
    nonce: bytes
    ciphertext: bytes

    def serialise(self) -> str:
        encode = lambda part: base64.urlsafe_b64encode(part).decode("ascii")  # noqa: E731
        return ".".join(
            [SCHEME, encode(self.wrapped_key), encode(self.nonce), encode(self.ciphertext)]
        )

    @classmethod
    def parse(cls, blob: str) -> "Envelope":
        try:
            scheme, wrapped, nonce, ciphertext = blob.split(".")
        except ValueError as exc:
            raise DecryptionError("malformed ciphertext") from exc
        if scheme != SCHEME:
            raise DecryptionError(f"unknown encryption scheme {scheme!r}")
        decode = base64.urlsafe_b64decode
        return cls(decode(wrapped), decode(nonce), decode(ciphertext))


def _wrap(data_key: bytes, master_key: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(master_key).encrypt(nonce, data_key, None)


def _unwrap(wrapped: bytes, master_key: bytes) -> bytes:
    nonce, sealed = wrapped[:NONCE_BYTES], wrapped[NONCE_BYTES:]
    try:
        return AESGCM(master_key).decrypt(nonce, sealed, None)
    except InvalidTag as exc:
        raise DecryptionError("could not unwrap the data key") from exc


def encrypt(plaintext: str, master_key: bytes, *, aad: bytes | None = None) -> str:
    """Encrypt one value. `aad` binds the ciphertext to its context.

    Passing the user id as `aad` means a row lifted from one user and pasted
    onto another fails to decrypt rather than silently working.
    """
    data_key = os.urandom(KEY_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext.encode("utf-8"), aad)
    return Envelope(_wrap(data_key, master_key), nonce, ciphertext).serialise()


def decrypt(blob: str, master_key: bytes, *, aad: bytes | None = None) -> str:
    envelope = Envelope.parse(blob)
    data_key = _unwrap(envelope.wrapped_key, master_key)
    try:
        plaintext = AESGCM(data_key).decrypt(envelope.nonce, envelope.ciphertext, aad)
    except InvalidTag as exc:
        raise DecryptionError("ciphertext failed authentication") from exc
    return plaintext.decode("utf-8")


class Secret:
    """A decrypted value that refuses to appear in logs or tracebacks.

    Refresh tokens are decrypted in memory at send time and nowhere else. The
    most likely way one escapes is not an attacker but a well-meant
    ``logger.info(f"{token=}")``, so the value is not reachable by accident.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "<Secret hidden>"

    __str__ = __repr__

    def __format__(self, _spec: str) -> str:
        return "<Secret hidden>"

    def __bool__(self) -> bool:
        return bool(self._value)
