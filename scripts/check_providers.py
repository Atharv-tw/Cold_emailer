"""Make one real call to each configured provider and report what happened.

Every provider in this app is tested against response shapes taken from
documentation rather than from the provider. That is enough to pin the
decision logic, and not enough to prove the request shape is right - and the
request shape is exactly what moves when a vendor ships a new API.

Run this the moment you paste a key in, before wondering why an upload fails:

    python scripts/check_providers.py

It costs one Gemini call and one verification credit. Nothing is written to
the database and no email is sent.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "core"))

from app.services.gemini import AIError, GeminiClient  # noqa: E402
from app.services.verification import EmailVerifier  # noqa: E402
from app.settings import get_settings  # noqa: E402

OK = "  ok    "
FAIL = "  FAIL  "
SKIP = "  skip  "

RESUME = """\
Dana Sharma
Backend engineer, distributed systems
github.com/dana

EXPERIENCE
ExampleCorp - Senior Engineer, 2023 to present
Cut p99 latency on the ingest path from 800ms to 90ms.

EDUCATION
BSc Computer Science, University of Somewhere, 2022
"""


async def check_gemini(settings, api_key: str | None) -> bool:
    # Gemini is BYOK: the server holds no key of its own, so there is nothing
    # to smoke-test unless one is passed on the command line for this check.
    if not api_key:
        print(f"{SKIP}gemini      BYOK - pass a key with --gemini-key to smoke-test it")
        return True

    client = GeminiClient(
        api_key=api_key,
        model=settings.gemini_model,
        endpoint=settings.gemini_endpoint,
    )
    print(f"        gemini      model {settings.gemini_model}")

    # Structured extraction is the call most likely to break on a model
    # change, because it is the one using generationConfig fields that the
    # newer Interactions API replaced.
    try:
        parsed = await client.parse_resume(RESUME)
    except AIError as exc:
        print(f"{FAIL}gemini      {exc}")
        return False

    name = str(parsed.get("name", ""))
    if "Dana" not in name:
        print(f"{FAIL}gemini      structured output came back without the name: {parsed!r}")
        return False

    print(f"{OK}gemini      structured extraction works (read {name!r})")
    return True


async def check_verifier(settings) -> bool:
    if not settings.quickemailverification_api_key:
        print(f"{SKIP}verifier    no API key set - addresses will come back 'unknown'")
        print("             That is a supported state: nothing is blocked, and the")
        print("             free syntax and MX checks still catch most typos.")
        return True

    verifier = EmailVerifier(
        api_key=settings.quickemailverification_api_key,
        endpoint=settings.quickemailverification_endpoint,
    )
    result = await verifier.verify("nonexistent-mailbox-9x7q@gmail.com")

    if result.source == "error":
        print(f"{FAIL}verifier    {result.reason}: {result.detail}")
        return False

    print(f"{OK}verifier    reachable (returned {result.status!r} via {result.source})")
    return True


async def check_dns() -> bool:
    from app.services.verification import has_mx

    if await has_mx("gmail.com") is not True:
        print(f"{FAIL}dns         cannot resolve MX for gmail.com - the free pre-check is dead")
        return False
    if await has_mx("nxdomain-9x7q.invalid") is not False:
        print(f"{FAIL}dns         a domain with no MX did not come back as False")
        return False
    print(f"{OK}dns         MX pre-check works")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-key", default="", help="Key to smoke-test - Gemini has no server-side key anymore")
    args = parser.parse_args()

    settings = get_settings()
    print(f"\nreading {ROOT / '.env'}\n")

    results = [
        await check_dns(),
        await check_gemini(settings, args.gemini_key),
        await check_verifier(settings),
    ]

    missing = [
        name
        for name, value in (
            ("GOOGLE_CLIENT_ID", settings.google_client_id),
            ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
            ("MASTER_KEY", settings.master_key),
            ("SESSION_SECRET", settings.session_secret),
            ("RECIPIENT_GUARD_SECRET", settings.recipient_guard_secret),
        )
        if not value
    ]
    if missing:
        print(f"\n{FAIL}config      not set: {', '.join(missing)}")
        results.append(False)

    print()
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
