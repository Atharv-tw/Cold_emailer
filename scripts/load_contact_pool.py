"""Seed the shared contact pool from a startup export.

    python scripts/load_contact_pool.py startup.json --dry-run
    python scripts/load_contact_pool.py startup.json

The source is a list of startups, each with an embedded `startup_employees`
array. The pool is a flat list of *people*, so the company fields are
denormalised onto each person on the way in: 253 companies to 507 people is a
small repeat, the list is curated and changes rarely, and a flat row is what
the rest of the product already reads.

**This cannot run on the application's connection.** A pool row has
`owner_user_id IS NULL`, the INSERT policy on `contacts` only admits rows the
session owns, and FORCE means being the table owner is not enough either. It
needs a role with BYPASSRLS - `neondb_owner` on Neon, the superuser locally -
supplied separately as POOL_LOADER_DATABASE_URL. Running as the app role fails
with InsufficientPrivilege, which is the policy working, not a bug.

Verification here is the free half only: an MX lookup per domain, no paid API.
That catches domains that do not exist at all - the transcription errors in
this data, like `putope.io` for `plutope.io` - without spending credits on
mailboxes that a real send will confirm or deny anyway. Addresses whose domain
disagrees with the company's own website are marked `risky` rather than
dropped: some are legitimate, and the bounce path resolves the rest for free.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "core"))

from app.services.verification import has_mx, normalise, syntax_ok  # noqa: E402

# --------------------------------------------------------------- derivations

# The source `role` is free text. Everything founder-shaped collapses to one
# value because that is the only distinction the product draws.
_FOUNDER_ROLES = {
    "co-founder", "cofounder", "founder", "ceo", "cto", "coo",
    "founder & ceo", "co-founder & ceo", "founder's office", "founders office",
    "managing director", "md",
}
_HIRING_ROLES = {"hr", "recruiter", "talent", "people", "hiring manager"}

# `sector` in this export is overloaded: alongside real sectors it carries
# curation buckets - Trending, Core, YC, Shark Tank, Community - which say how
# the list was assembled, not what the company does. Those map to `other`; the
# real sector for those rows is simply absent from the source.
_SECTORS = {
    "ai": "ai",
    "fintech": "fintech",
    "edtech": "edtech",
}

_US_CITIES = ("san francisco", "new york", "seattle", "austin", "boston", "usa")


def target_type_for(role: str) -> str:
    cleaned = role.strip().lower()
    if cleaned in _HIRING_ROLES:
        return "hiring_manager"
    if cleaned in _FOUNDER_ROLES:
        return "founder"
    # Blank, "-", and the long tail. This is a list of startup founders, so
    # `founder` is the honest default rather than an empty string.
    return "founder"


def company_type_for(sector: str) -> str:
    return _SECTORS.get(sector.strip().lower(), "other")


def timezone_for(location: str) -> str:
    cleaned = location.strip().lower()
    if any(city in cleaned for city in _US_CITIES):
        return "America/Los_Angeles"
    # Everything else in this dataset is an Indian city, written a dozen ways
    # (Bengaluru / Bengaluru, Karnataka / Bangalore, India / ...).
    return "Asia/Kolkata"


def host_of(url: str) -> str:
    if not url:
        return ""
    host = re.sub(r"^https?://", "", url.strip().lower()).split("/")[0]
    return host[4:] if host.startswith("www.") else host


def domains_agree(email_domain: str, website_host: str) -> bool:
    """Whether an address plausibly belongs to the company's own domain."""
    if not website_host or not email_domain:
        return True  # nothing to disagree with
    return (
        email_domain == website_host
        or email_domain.endswith("." + website_host)
        or website_host.endswith("." + email_domain)
    )


FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "outlook.com",
    "hotmail.com", "icloud.com", "proton.me", "protonmail.com",
}


# ------------------------------------------------------------------ flatten


def flatten(startups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per person, company fields denormalised down, deduplicated.

    The source holds a handful of addresses twice (the same founder listed
    under two companies). First occurrence wins - the pool's partial unique
    index would reject the second anyway, and failing the whole load over a
    known quirk of the data helps nobody.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for startup in startups:
        website = startup.get("website") or ""
        for person in startup.get("startup_employees") or []:
            email = normalise(person.get("email") or "")
            if not email or not syntax_ok(email):
                continue
            if email in seen:
                continue
            seen.add(email)

            linkedin = (person.get("linkedin_url") or "").strip()
            rows.append(
                {
                    "source_id": str(person.get("id") or ""),
                    "name": (person.get("name") or "").strip(),
                    "email": email,
                    "role": (person.get("role") or "").strip(),
                    "links": {"linkedin": linkedin} if linkedin else {},
                    "company": (startup.get("name") or "").strip(),
                    "company_description": (startup.get("description") or "").strip(),
                    "company_website": website.strip(),
                    "target_type": target_type_for(person.get("role") or ""),
                    "company_type": company_type_for(startup.get("sector") or ""),
                    "timezone": timezone_for(startup.get("location") or ""),
                }
            )
    return rows


# ------------------------------------------------------------- verification


async def verify(rows: list[dict[str, Any]]) -> None:
    """Attach a `verification` verdict to each row, in place.

    One MX lookup per *domain*, not per row - 507 people share ~231 domains,
    and the resolver has no more to say the second time.
    """
    domains = sorted({row["email"].split("@")[-1] for row in rows})
    results = await asyncio.gather(*(has_mx(domain) for domain in domains))
    mx = dict(zip(domains, results))

    for row in rows:
        domain = row["email"].split("@")[-1]
        website_host = host_of(row["company_website"])

        if mx.get(domain) is False:
            row["verification"] = {
                "state": "undeliverable",
                "reason": "no_mx",
                "detail": f"{domain} publishes no mail exchanger",
                "source": "pool_loader",
            }
        elif domain in FREE_PROVIDERS:
            row["verification"] = {
                "state": "risky",
                "reason": "free_provider",
                "detail": "a personal address rather than a company one",
                "source": "pool_loader",
            }
        elif not domains_agree(domain, website_host):
            row["verification"] = {
                "state": "risky",
                "reason": "domain_mismatch",
                "detail": f"{domain} is not {website_host}, so it may be a typo",
                "source": "pool_loader",
            }
        else:
            # MX exists, or DNS could not answer. Neither is proof the mailbox
            # is real - only a send is - so this stays `unknown` rather than
            # claiming a confidence the check cannot support.
            row["verification"] = {
                "state": "unknown",
                "reason": "mx_only",
                "detail": "the domain accepts mail; the mailbox is unconfirmed",
                "source": "pool_loader",
            }


# ------------------------------------------------------------------- writing


def loader_dsn() -> str:
    """A connection that can write rows nobody owns.

    Defaults to MIGRATION_DATABASE_URL, which already points at the owning
    role for exactly this reason - it is the connection that runs migrations,
    and the pool needs the same privilege for the same cause. Only set
    POOL_LOADER_DATABASE_URL if seeding should use a different role.
    """
    dsn = (
        os.environ.get("POOL_LOADER_DATABASE_URL", "").strip()
        or os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    )
    if not dsn:
        sys.exit(
            "Neither POOL_LOADER_DATABASE_URL nor MIGRATION_DATABASE_URL is set.\n"
            "A pool row is owned by nobody, and the contacts INSERT policy only\n"
            "admits rows the session owns - so seeding needs a role with\n"
            "BYPASSRLS (neondb_owner on Neon, the superuser locally). The\n"
            "application's own role is refused, which is the policy working."
        )
    return dsn.replace("postgresql+psycopg://", "postgresql://")


def write(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Upsert every row. Returns (inserted, updated)."""
    import psycopg
    from psycopg.types.json import Jsonb

    inserted = updated = 0
    with psycopg.connect(loader_dsn()) as connection:
        with connection.cursor() as cursor:
            _assert_can_write_the_pool(cursor)
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO contacts (
                        id, owner_user_id, name, email, role, links,
                        company, company_description, company_website,
                        target_type, company_type, timezone, verification, source_id
                    ) VALUES (
                        gen_random_uuid(), NULL, %(name)s, %(email)s, %(role)s, %(links)s,
                        %(company)s, %(company_description)s, %(company_website)s,
                        %(target_type)s, %(company_type)s, %(timezone)s,
                        %(verification)s, %(source_id)s
                    )
                    ON CONFLICT (source_id) WHERE source_id <> '' DO UPDATE SET
                        name = EXCLUDED.name,
                        role = EXCLUDED.role,
                        links = EXCLUDED.links,
                        company = EXCLUDED.company,
                        company_description = EXCLUDED.company_description,
                        company_website = EXCLUDED.company_website,
                        target_type = EXCLUDED.target_type,
                        company_type = EXCLUDED.company_type,
                        timezone = EXCLUDED.timezone,
                        verification = EXCLUDED.verification,
                        updated_at = now()
                    RETURNING (xmax = 0) AS was_inserted
                    """,
                    {**row, "links": Jsonb(row["links"]), "verification": Jsonb(row["verification"])},
                )
                result = cursor.fetchone()
                if result and result[0]:
                    inserted += 1
                else:
                    updated += 1
        connection.commit()
    return inserted, updated


def _assert_can_write_the_pool(cursor) -> None:
    """Fail before the first insert rather than partway through it."""
    cursor.execute(
        "SELECT current_user, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"
    )
    user, bypasses, is_super = cursor.fetchone()
    if not (bypasses or is_super):
        sys.exit(
            f"connected as {user!r}, which has neither BYPASSRLS nor superuser.\n"
            "The contacts INSERT policy will refuse every pool row. Point\n"
            "POOL_LOADER_DATABASE_URL at the owning role instead."
        )


def already_dead(rows: list[dict[str, Any]]) -> set[str]:
    """Addresses a bounce has already proved do not exist."""
    import psycopg

    with psycopg.connect(loader_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT email FROM dead_addresses WHERE email = ANY(%s)",
                ([row["email"] for row in rows],),
            )
            return {row[0] for row in cursor.fetchall()}


# ---------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=str(REPO_ROOT / "startup.json"))
    parser.add_argument("--dry-run", action="store_true", help="classify but write nothing")
    parser.add_argument("--limit", type=int, default=0, help="only the first N people")
    args = parser.parse_args()

    startups = json.loads(Path(args.source).read_text(encoding="utf-8"))
    rows = flatten(startups)
    if args.limit:
        rows = rows[: args.limit]

    print(f"{len(startups)} startups -> {len(rows)} unique people")

    if not args.dry_run:
        dead = already_dead(rows)
        if dead:
            rows = [row for row in rows if row["email"] not in dead]
            print(f"skipped {len(dead)} address(es) already known dead")

    asyncio.run(verify(rows))

    verdicts = Counter(row["verification"]["state"] for row in rows)
    reasons = Counter(row["verification"]["reason"] for row in rows)
    print("\nverification:")
    for state, count in verdicts.most_common():
        print(f"  {count:5}  {state}")
    print("\nreasons:")
    for reason, count in reasons.most_common():
        print(f"  {count:5}  {reason}")

    print("\nderived target_type: " + ", ".join(
        f"{v}={c}" for v, c in Counter(r["target_type"] for r in rows).most_common()
    ))
    print("derived company_type: " + ", ".join(
        f"{v}={c}" for v, c in Counter(r["company_type"] for r in rows).most_common()
    ))

    if args.dry_run:
        print("\ndry run - nothing written")
        return

    inserted, updated = write(rows)
    print(f"\nwrote pool: {inserted} inserted, {updated} updated")


if __name__ == "__main__":
    main()
