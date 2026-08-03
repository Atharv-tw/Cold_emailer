"""API package.

The one thing that has to happen before anything else on Windows: Python
defaults to ProactorEventLoop there, and psycopg refuses to run in async mode
on it. Every entry point into this package - Alembic, the arq worker, the test
suite - imports `app` before it creates a loop, so setting the policy here
fixes all of them at once.

Uvicorn is the exception and needs `run_api.py`, because it builds its loop
before importing the application.
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":  # pragma: no cover - platform-specific
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
