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
from pathlib import Path

if sys.platform == "win32":  # pragma: no cover - platform-specific
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _check_interpreter() -> None:
    """Fail early and legibly when started with the wrong Python.

    `python run_api.py` picks up whatever is on PATH, which on a machine with
    a system Python is usually not the project venv. The failure that produces
    is a ModuleNotFoundError forty frames deep inside uvicorn's reloader
    subprocess, which says nothing about the actual mistake.
    """
    venv = Path(__file__).resolve().parents[2] / ".venv"
    interpreter = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    if sys.prefix != sys.base_prefix or not venv.is_dir():
        return  # already in a virtualenv, or there is no venv to prefer

    sys.exit(
        f"\nThis is {sys.executable}, which is not the project venv, and the\n"
        f"dependencies are not installed there.\n\n"
        f"Run it with:\n\n    {interpreter} {Path(__file__).name} {' '.join(sys.argv[1:])}\n\n"
        f"or activate the venv first:\n\n"
        f"    {venv / ('Scripts/Activate.ps1' if os.name == 'nt' else 'bin/activate')}\n"
    )


_check_interpreter()

import uvicorn  # noqa: E402  - must follow the policy change and the check

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload="--reload" in sys.argv or os.environ.get("API_RELOAD") == "1",
        # Uvicorn's own loop setup puts Windows back on the proactor loop,
        # undoing the policy set above and taking psycopg with it. "none"
        # leaves the loop alone so asyncio.run honours the policy - the
        # symptom otherwise is a healthy server whose every query fails.
        loop="none",
    )
