"""Start the API.

Exists because of ordering. Uvicorn creates its event loop and only then
imports the application, so setting the loop policy inside `app/__init__.py`
happens too late to help it - the loop is already a ProactorEventLoop, and
psycopg fails on the first query rather than at startup, which is a
considerably worse place to find out.

    python run_api.py

Uvicorn's own CLI works fine on Linux and macOS; this is the portable way in.
"""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":  # pragma: no cover - platform-specific
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402  - must follow the policy change

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload="--reload" in sys.argv or os.environ.get("API_RELOAD") == "1",
    )
