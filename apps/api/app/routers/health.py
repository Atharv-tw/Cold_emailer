"""Liveness and readiness.

Readiness answers "would a request work right now", which for this service
means the database is reachable *and* the keys that protect stored refresh
tokens are actually configured. Starting up without a master key and only
discovering it at the first send is the failure mode this catches.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..db import SessionFactory
from ..deps import SettingsDep

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(settings: SettingsDep) -> dict[str, object]:
    checks: dict[str, object] = {}

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - the reason is the useful part
        checks["database"] = f"{type(exc).__name__}: {exc}"

    for name, configured in (
        ("master_key", bool(settings.master_key)),
        ("session_secret", bool(settings.session_secret)),
        ("recipient_guard_secret", bool(settings.recipient_guard_secret)),
        ("google_client_id", bool(settings.google_client_id)),
    ):
        checks[name] = "ok" if configured else "missing"

    checks["ready"] = all(value == "ok" for value in checks.values())
    return checks
