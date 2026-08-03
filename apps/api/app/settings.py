"""Runtime configuration, entirely from the environment.

There is no config file. The single-user CLI had one because there was one
user; a multi-tenant service reads secrets from the environment and everything
else from the database, so that a user's sending window is a row they can edit
rather than a file only the operator can.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env at the repo root, found regardless of where the process was
# started from. Alembic runs in apps/api, uvicorn is usually started there
# too, and the worker anywhere - a CWD-relative path silently loads nothing
# and leaves you debugging an empty MASTER_KEY.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later entries win, so a local .env can still override the root one.
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = False

    database_url: str = "postgresql+psycopg://outreach:outreach@localhost:5432/outreach"
    redis_url: str = "redis://localhost:6379/0"

    # Where the web app runs. Used for CORS and the OAuth redirect.
    web_origin: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""

    # Signs our own session tokens. Not the same key as anything Google issues.
    session_secret: str = ""
    session_ttl_minutes: int = 60 * 24 * 14

    # Envelope-encryption master key: 32 raw bytes, base64-encoded.
    # Generate with:  python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
    master_key: str = ""

    # Keys the cross-user recipient guard. Deliberately separate from
    # master_key and from the database, so possession of the table alone does
    # not reveal which addresses it covers.
    recipient_guard_secret: str = ""

    # https://quickemailverification.com - the free tier is 100 checks a day,
    # which is comfortably more than this product's caps allow anyone to send.
    quickemailverification_api_key: str = ""
    quickemailverification_endpoint: str = (
        "https://api.quickemailverification.com/v1/verify"
    )

    gemini_api_key: str = ""
    # 3.6 Flash went GA on 2026-07-21. `generateContent` is explicitly still
    # fully supported for it - the newer Interactions API is recommended for
    # new projects but is not a requirement, and moving to it would change the
    # request shape rather than just the model string.
    gemini_model: str = "gemini-3.6-flash"
    gemini_endpoint: str = "https://generativelanguage.googleapis.com/v1beta"

    # projects/<project>/topics/<topic>. The Gmail service account must have
    # Publisher on it, or users.watch fails with a permission error that reads
    # as though the scope is wrong.
    gmail_pubsub_topic: str = ""
    # Shared secret in the push endpoint's URL, so an open POST route cannot be
    # used to make us hammer Gmail on someone else's behalf.
    pubsub_verification_token: str = ""

    # Web push. Generate a pair once and keep them:
    #   npx web-push generate-vapid-keys
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:noreply@example.com"

    storage_dir: str = "./var/storage"

    @field_validator("session_secret", "recipient_guard_secret")
    @classmethod
    def _secret_is_long_enough(cls, value: str, info) -> str:
        # HMAC-SHA256 keys shorter than the hash output weaken the MAC, and
        # PyJWT warns about it at runtime rather than refusing. Fail at startup
        # instead of shipping a session token anyone can grind.
        if value and len(value.encode("utf-8")) < 32:
            raise ValueError(
                f"{info.field_name.upper()} must be at least 32 bytes. "
                'Generate one with: python -c "import secrets;print(secrets.token_urlsafe(48))"'
            )
        return value

    @field_validator("master_key")
    @classmethod
    def _master_key_is_32_bytes(cls, value: str) -> str:
        if not value:
            return value
        try:
            raw = base64.b64decode(value, validate=True)
        except Exception as exc:  # noqa: BLE001 - surface the real problem
            raise ValueError("MASTER_KEY must be base64-encoded") from exc
        if len(raw) != 32:
            raise ValueError(f"MASTER_KEY must decode to 32 bytes, got {len(raw)}")
        return value

    @property
    def master_key_bytes(self) -> bytes:
        if not self.master_key:
            raise RuntimeError(
                "MASTER_KEY is unset. Refresh tokens cannot be encrypted, and "
                "storing them in the clear is not an option. Generate one with: "
                'python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"'
            )
        return base64.b64decode(self.master_key)

    @property
    def recipient_guard_secret_bytes(self) -> bytes:
        if not self.recipient_guard_secret:
            raise RuntimeError("RECIPIENT_GUARD_SECRET is unset")
        return self.recipient_guard_secret.encode("utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
