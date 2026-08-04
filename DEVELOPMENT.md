# Development

## Layout

```
apps/api          FastAPI. Auth, profiles, targets, generation, worker.
apps/web          Next.js + React. The site, and later the PWA layer.
packages/core     Ported deliverability logic: scheduling, limits, threading, classification.
infra             docker-compose (Postgres, Redis).
```

The single-user CLI is gone. What survived is in `packages/core`; the
spreadsheet reader survived as `apps/api/app/services/sheets.py`, unused until
bulk import lands. Everything else — `config.py`, `store.py`, `cli.py`,
`panel.py`, `tracker.py`, `sequences/` — assumed one person with one config
file and had no place here.

## Product phases

The product is being finished in phases so each slice can be reviewed and
tested without turning the codebase into a moving target.

### Phase 1 - template and evidence control

Status: in progress.

Implemented in this phase:

- selectable generation templates exposed by `GET /v1/templates`
- draft generation accepts `template_key`
- profile projects have `categories` and `best_for` metadata
- generation ranks projects against the target before building the prompt
- profile UI exposes project tech, URL, categories, and best-fit audience
- docs updated to match the current implementation

Deferred intentionally:

- user-authored templates and template version history
- persisted "selected project" metadata on each generated draft

### Phase 2 - import and workflow dashboard

Planned:

- CSV/XLSX import endpoint and mapping UI using `services/sheets.py`
- duplicate/suppression/verification preview before saving imported targets
- target table filters for status, target type, company type, and intent
- workflow lanes for draft, scheduled, active, replied, paused, completed

### Phase 3 - calendar reminders

Planned:

- Google Calendar reminder integration
- reminder event creation for scheduled follow-ups
- event update/cancel when a reply, bounce, opt-out, or manual stop occurs
- dashboard and web push remain the fallback reminder system

### Phase 4 - analytics and production hardening

Planned:

- reply rate, bounce rate, scheduled volume, and stale-sequence analytics
- worker health/status UI
- Gmail watch health and last reconcile timestamps
- frontend regression tests
- production deployment checklist

## packages/core

The part of the CLI worth keeping: warmup ramps, business-day scheduling, send
windows, threading headers, and reply/bounce/auto-responder classification.

It has **no dependencies on purpose**. It is the regression net for the
rewrite, so it must be runnable on a clean checkout:

```bash
python -m unittest discover -s packages/core/tests
```

What changed in the port:

- Every function takes a per-user `SendingWindow` or policy object instead of
  reaching into a global `Config`. There is no global config any more.
- `build_footer` is gone. Personal mail carries no CAN-SPAM block, and no
  `List-Unsubscribe` header - it makes a one-to-one note read as a blast.
- Open-tracking pixels are gone with it.
- `build_message` no longer sets its own `Message-ID`. Gmail assigns one, and
  that assigned value is what has to be stored and threaded against.
- Classification checks for an auto-responder **before** opt-out phrases.
  Vacation replies routinely carry a corporate footer containing the word
  "unsubscribe", and the old order would permanently suppress someone who was
  merely on leave.
- `recipient_key` is a keyed HMAC rather than a bare hash. A plain hash of an
  email address is trivially reversible by dictionary attack, so it would not
  have given the cross-user guard the privacy property it claims.

## Running it

```bash
docker compose -f infra/docker-compose.yml up -d
```

```bash
cp .env.example .env
```

Fill in `.env`. The three generated secrets:

```bash
python -c "import os,base64;print('MASTER_KEY=' + base64.b64encode(os.urandom(32)).decode())"
```

```bash
python -c "import secrets;print('SESSION_SECRET=' + secrets.token_urlsafe(48))"
```

```bash
python -c "import secrets;print('RECIPIENT_GUARD_SECRET=' + secrets.token_urlsafe(48))"
```

`RECIPIENT_GUARD_SECRET` keys the cross-user pile-on guard. Keep it out of the
database's own secret store: the guard's privacy property depends on the table
being useless to whoever holds it without this value. Rotating it resets the
guard.

Then:

Activate the venv first, or every command below picks up whatever `python` is
on PATH — usually a system install without these dependencies:

```bash
.venv/Scripts/Activate.ps1
```

```bash
pip install -e packages/core
```

```bash
pip install -e apps/api
```

```bash
cd apps/api && alembic upgrade head
```

```bash
cd apps/api && python run_api.py --reload
```

```bash
cd apps/web && npm install && npm run dev
```

`GET /readyz` reports whether the database is reachable and whether the keys
that protect stored refresh tokens are actually configured.

## Google OAuth

One OAuth client (Web application), used by both apps. The consent screen stays
in **testing** mode: up to 100 users, no CASA review, and `gmail.readonly`
works from day one.

**Every account that signs in must be added by hand** under *APIs & Services →
OAuth consent screen → Audience → Test users*. This is not the soft
"unverified app" warning — an account that is not on the list gets
`Error 403: access_denied` and cannot proceed at all. Adding it takes effect
immediately. That list is what the 100-user cap actually counts.

Approved testers still see the "unverified app" warning, which is expected and
which onboarding explains before they hit it.

Scopes: `openid email profile`, `gmail.send`, `gmail.readonly`.

`gmail.readonly` is what makes reply tracking possible. Google's consent screen
lets people untick individual scopes, and an account that can send but cannot
see replies is the one state this product must never run in silently — so the
API reports missing scopes and the dashboard asks the user to grant them again.

## Row-level security

Every user-owned table has `user_id`, every query filters on it, and Postgres
RLS enforces the same thing again. The duplication is the point: the query
filter makes the product correct, RLS makes a forgotten filter fail closed.

Sessions announce who they are with `SELECT set_config('app.user_id', ..., true)`,
which the policies compare against. A session that never sets it sees nothing.

**Two database roles, and this is not optional.** Superusers bypass RLS
outright, and `FORCE ROW LEVEL SECURITY` does not change that — so an
application connecting as the schema owner sees every row of every user's data
however carefully the policies are written. That was true here until it was
tested against a live database.

```
outreach       owns the schema, runs migrations, superuser
outreach_app   what the API and worker connect as, no bypass, DML only
```

`DATABASE_URL` uses the second; `MIGRATION_DATABASE_URL` uses the first. The
application cannot drop the policies that constrain it, and `test_rls.py`
asserts that along with the isolation itself.

On Windows, `app/__init__.py` switches asyncio to the selector event loop —
psycopg refuses to run async on the default proactor loop. Uvicorn builds its
loop before importing the app, so start the API with `python run_api.py`
rather than the uvicorn CLI.

Sign-in is the exception, because it has to find a user before there is a user
to bind to. Rather than a `BYPASSRLS` role - which would exempt every query on
that connection - there is one `SECURITY DEFINER` function,
`find_user_id_by_google_sub`, that returns an id and nothing else.

## The worker

The API alone does not send anything. `app.worker` holds four jobs:

| job | cadence | why it exists |
|---|---|---|
| `tick` | every 2 min | sends what is due |
| `renew_watches` | daily | Gmail's `watch` expires in ~7 days and then stops delivering **silently** — no error, no callback. Nothing tells us when it lapses, so it is re-armed every day regardless. |
| `reconcile` | 4×/day | reads threads directly for anything push missed. Slow, so it runs rarely; it is what makes a broken push pipeline survivable rather than dangerous. |
| `notify_due` | daily | web push for follow-ups coming due |

```bash
cd apps/api && arq app.worker.WorkerSettings
```

This is why the API needs a long-running host rather than a serverless one.

## Gmail push

1. Create a Pub/Sub topic.
2. Grant `gmail-api-push@system.gserviceaccount.com` the **Publisher** role on
   it. Without this, `users.watch` fails with a permission error that reads as
   though the scope is wrong.
3. Create a push subscription pointing at
   `<API_BASE_URL>/v1/gmail/push?token=<PUBSUB_VERIFICATION_TOKEN>`.

The token is not decoration. Google posts to that endpoint, not a signed-in
user, so without it the route is an open POST anyone could use to make this
service hammer Gmail.

Reply detection is thread-based: any message in the target's thread not
authored by the user is inbound. That is more reliable than matching
Message-IDs, which clients drop and rewrite.

## Address verification

QuickEmailVerification. Syntax and MX are checked first so obvious typos never
cost a credit, and the free tier's 100 checks a day is far more than this
product's own caps let anyone send.

Four states, and the mapping is deliberate:

- `undeliverable` blocks sending
- `risky` warns and lets the user proceed — a catch-all domain lands here,
  because "valid" there only means the server did not say no
- `unknown` gets out of the way
- **every one of our own failures maps to `unknown`** — timeout, no credits,
  rate limit, bad key. A vendor outage is not evidence about somebody's
  address, and blocking a send on it would be inventing a fact.

## The PWA

`app/manifest.ts` plus `public/sw.js`. No separate build, no store.

The service worker caches nothing on purpose: a cold-outreach dashboard
showing stale state is worse than one that fails to load, because the entire
product depends on "have they replied yet" being current.

Web push is a convenience. The dashboard's "due today" list is the mechanism,
and it works for everyone who denied notifications, revoked them, or is on a
platform that silently drops them.

## Tests

```bash
python -m unittest discover -s packages/core/tests
```

```bash
python -m unittest discover -s apps/api/tests
```

190 tests, no network and no database. The Gmail transport, Gemini and the
verifier are all driven through injected `httpx` transports against real
response shapes.

Not covered by these: anything that needs Postgres. `send_one` runs every
limit check in sequence against live rows, and the end-to-end proof of it is
the manual run in the plan — a throwaway Google account, a target pointing at
a second address you own, reply from it, confirm the sequence stops; then
repeat with an out-of-office and confirm it **defers instead of stopping**.
