# Deployment

A checklist for standing this up somewhere real. It assumes the architecture in
`DEVELOPMENT.md`: a FastAPI service, a long-running `arq` worker sharing that
codebase, Postgres, Redis, a Next.js front end, and one Google OAuth client.

Nothing here is serverless-shaped. The worker has to run continuously, and the
API needs a host that stays up between requests.

## 1. Secrets

Generate these once and keep them somewhere durable. Losing `MASTER_KEY` means
every stored Google refresh token becomes undecryptable and every user has to
reconnect; rotating `RECIPIENT_GUARD_SECRET` resets the cross-user guard.

```bash
python -c "import os,base64;print('MASTER_KEY=' + base64.b64encode(os.urandom(32)).decode())"
python -c "import secrets;print('SESSION_SECRET=' + secrets.token_urlsafe(48))"
python -c "import secrets;print('RECIPIENT_GUARD_SECRET=' + secrets.token_urlsafe(48))"
python -c "import secrets;print('PUBSUB_VERIFICATION_TOKEN=' + secrets.token_urlsafe(24))"
npx web-push generate-vapid-keys   # VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
```

`SESSION_SECRET` and `RECIPIENT_GUARD_SECRET` must be at least 32 bytes or the
API refuses to start - a short HMAC key is a session token anyone can grind.
`MASTER_KEY` must decode to exactly 32 bytes.

## 2. Environment variables

Read from one `.env` at the repo root (see `.env.example`). The API and the
worker must share it.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | App role, **not** the owner. `postgresql+psycopg://outreach_app:…` |
| `MIGRATION_DATABASE_URL` | yes | Schema owner. Used only by Alembic. |
| `REDIS_URL` | yes | Worker queue. |
| `WEB_ORIGIN` | yes | Public URL of the web app. CORS + calendar event links. |
| `API_BASE_URL` | yes | Public URL of the API. Used in the Pub/Sub push subscription. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | yes | One OAuth Web client, shared by both apps. |
| `SESSION_SECRET` | yes | Signs our own session tokens. ≥32 bytes. |
| `MASTER_KEY` | yes | Encrypts refresh tokens at rest. 32 bytes, base64. |
| `RECIPIENT_GUARD_SECRET` | yes | Keys the cross-user pile-on guard. ≥32 bytes. |
| `GEMINI_API_KEY` | yes | Draft generation and resume parsing. |
| `QUICKEMAILVERIFICATION_API_KEY` | recommended | Address verification. Without it, verification returns `unknown` (never blocks). |
| `GMAIL_PUBSUB_TOPIC` | for push | `projects/<project>/topics/<topic>`. Without it, reply detection falls back to the reconcile sweep. |
| `PUBSUB_VERIFICATION_TOKEN` | for push | Shared secret in the push URL. |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` | for web push | Optional; the dashboard "due today" list is the real mechanism. |
| `STORAGE_DIR` | yes | Where uploaded resumes are written before parsing. |
| `ENVIRONMENT` | yes | Set to `production`; makes the session cookie `Secure`. |

`GET /readyz` reports whether the database is reachable and whether
`MASTER_KEY`, `SESSION_SECRET`, `RECIPIENT_GUARD_SECRET` and `GOOGLE_CLIENT_ID`
are actually set. Wire it to your load balancer's health check.

The web app additionally needs `AUTH_SECRET` (Auth.js), `API_BASE_URL`, and the
Google client credentials in its own environment.

## 3. Database

Two roles, and this is not optional - a superuser or the schema owner bypasses
row-level security outright, so the API must connect as a role that cannot:

```sql
CREATE ROLE outreach LOGIN PASSWORD '…';            -- owns the schema, runs migrations
CREATE ROLE outreach_app LOGIN PASSWORD '…';        -- what the API/worker connect as
CREATE DATABASE outreach OWNER outreach;
```

`outreach_app` needs `USAGE` on the schema and DML on the tables; migration
`0002` grants that and turns RLS on for every user-scoped table. Run migrations
with the owner URL:

```bash
cd apps/api && MIGRATION_DATABASE_URL=… alembic upgrade head
```

Migrations, newest last: `0001` schema, `0002` app role + RLS, `0003` project
metadata, `0004` calendar event tracking, `0005` worker heartbeat. `test_rls.py`
asserts the isolation and that the app role cannot drop its own policies; run it
against a throwaway database before trusting a new environment.

## 4. Redis and the worker

Redis backs the `arq` queue. The worker is a separate long-running process:

```bash
cd apps/api && arq app.worker.WorkerSettings
```

Run exactly the environment the API runs with. If the worker is down, nothing
sends and replies go unnoticed - `/ops` reports `worker_running: false` once the
`tick` heartbeat is older than ten minutes, so alert on that.

Exactly one worker. Two processes against the same database means `tick` fires
twice every two minutes, and `MAX_SENDS_PER_TICK` is a per-process cap - so a
second worker silently doubles the send rate past a limiter that was never
consulted about it. Before starting a worker anywhere, read `worker_heartbeat`:
a recent `tick` means one is already running somewhere else.

### Running it on a host separate from the API

This describes the split topology - API on a managed platform, worker on its
own box - which is **not** the current arrangement; see "Running the whole
stack on one host" below. It is kept because `infra/outreach-worker.service`
is the rollback path, and because the constraints in it still apply to any
host running the worker.

The worker takes no inbound connections - it only dials out to Postgres and
Redis - so when both are managed services it needs no reverse proxy, no
published port, and no container. A systemd unit is enough.

```bash
uv python install 3.10 && uv venv --python 3.10 .venv
uv pip install --python .venv -e ./packages/core -e ./apps/api
```

3.10 explicitly: that is what the suite passes on, and a current Ubuntu ships
something far newer. The installs are **editable on purpose** - `settings.py`
derives `REPO_ROOT` from `parents[3]` of its own path to find the root `.env`,
and a site-packages install resolves that to somewhere inside the interpreter.

Two things about that host's `.env`:

- `WEB_ORIGIN` must be the real web origin. `sync_calendars` writes it into
  Google Calendar events, so a development value puts dead links in real
  calendars.
- Omit `MIGRATION_DATABASE_URL`. The worker never runs Alembic, and that URL is
  the schema owner - a role that bypasses RLS outright. It has no reason to sit
  on a machine that only runs jobs.

Confirm before starting, not after. This reaches both services and sends
nothing - it prints the heartbeat table, which doubles as the check for whether
a worker is already running elsewhere:

```bash
cd apps/api && ../../.venv/bin/python -c "
import asyncio
from sqlalchemy import text
from app.db import SessionFactory
from app.settings import get_settings
from arq.connections import RedisSettings, create_pool

async def main():
    async with SessionFactory() as s:
        for r in (await s.execute(text('select job, at, detail from worker_heartbeat order by at desc'))).all():
            print(r.job, r.at, '|', r.detail)
    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    print('redis ping:', await pool.ping())

asyncio.run(main())
"
```

Upstash restricts `INFO`, so arq's startup line reports `redis_version=?` and
`mem_usage=?`. That is cosmetic; `db_keys` coming through means the connection
is fine. Note that `schedule` is under
RLS, so an unbound session sees zero rows rather than the truth - count pending
work with the owner credential from somewhere else, and know how much is
overdue before you start, or the first few ticks flush the entire backlog at
once.

Managed Redis is usually billed per command, and arq polls continuously -
`poll_delay` defaults to 0.5s, so an idle worker issues on the order of 170k
commands a day doing nothing. Raising it to `5.0` cuts that roughly tenfold and
costs only a few seconds of enqueue latency, which no job here is sensitive to.

### Running the whole stack on one host (Docker Compose)

The current arrangement. Postgres, Redis, the API and the worker run as one
compose project on a self-hosted box; only the web app stays on Vercel.
`infra/docker-compose.prod.yml` is that stack, and both Python services share
the single image built by `infra/Dockerfile.api`.

What this buys: no cold starts, no per-command Redis billing, and no storage
ceiling. What it costs: the host is now a single point of failure for the whole
product rather than just for sending, and backups become yours (section 8).

```bash
docker compose -f infra/docker-compose.prod.yml --env-file .env up -d postgres redis
docker compose -f infra/docker-compose.prod.yml --env-file .env run --rm api alembic upgrade head
docker compose -f infra/docker-compose.prod.yml --env-file .env up -d --build api worker
```

Run it from the repo root. Compose resolves `${POSTGRES_PASSWORD}` against the
project directory, which would otherwise be `infra/` - `--env-file` sets where
that interpolation reads from, while the `env_file:` inside the compose file is
what the containers themselves get.

Four things that are easy to get wrong here:

- **`APP_DB_PASSWORD` must be set before migrating.** Migration `0002` reads it
  when creating `outreach_app` and falls back to the literal string
  `outreach_app`.
- **The image installs editable, and the repo layout inside it is
  load-bearing.** `settings.py` derives `REPO_ROOT` from `parents[3]` of its own
  path; flattened into site-packages that resolves inside the interpreter.
- **Exactly one worker, still.** Before starting the compose worker, confirm no
  systemd unit and no stray `arq` process is running against the same database -
  `MAX_SENDS_PER_TICK` is per-process, so a second one doubles the send rate
  past a limiter that never sees it.
- **Neither Postgres nor Redis publishes a port.** The dev `docker-compose.yml`
  maps 5432 with the password `outreach`, which is fine on a laptop and would be
  an open database on a shared network. Only the API publishes, and only on
  `127.0.0.1`.

### Reaching it from the internet

The API needs a public HTTPS origin: Vercel's servers cannot reach a private
address, and Google posts Pub/Sub notifications from the internet. Either a
reverse proxy with a certificate, or a Cloudflare tunnel - see
`infra/cloudflared-ingress.yml` for the tunnel form, which needs neither a
certificate nor an open inbound port.

Whatever sits in front terminates TLS and forwards plain HTTP, which is why
uvicorn runs with `--proxy-headers`. Note that traffic reaching a published
container port arrives from the Docker bridge gateway, not `127.0.0.1`, so
`--forwarded-allow-ips` cannot be narrowed to loopback; binding the published
port to `127.0.0.1` is what limits who can reach it.

Only `API_BASE_URL` changes when the API moves. The OAuth redirect URI is
derived from `WEB_ORIGIN`, so as long as the web app stays put, nothing in the
Google Console needs touching except the Pub/Sub push subscription.

## 5. Google OAuth

One OAuth client (Web application). The consent screen stays in **testing** mode:
up to 100 users, no CASA review, `gmail.readonly` from day one.

- Authorized redirect URI: `<WEB_ORIGIN>/api/auth/callback/google`.
- Scopes: `openid email profile`, `gmail.send`, `gmail.readonly`, and the
  optional `calendar.events`.
- **Every account that signs in must be added by hand** under *APIs & Services →
  OAuth consent screen → Audience → Test users*. An account not on the list gets
  `Error 403: access_denied` and cannot proceed. That list is what the 100-user
  cap counts.

## 6. Gmail push (Pub/Sub)

1. Create a Pub/Sub topic; set `GMAIL_PUBSUB_TOPIC` to its full name.
2. Grant `gmail-api-push@system.gserviceaccount.com` the **Publisher** role on
   it, or `users.watch` fails with an error that reads like a scope problem.
3. Create a push subscription pointing at
   `<API_BASE_URL>/v1/gmail/push?token=<PUBSUB_VERIFICATION_TOKEN>`.

The token is not decoration: Google posts there, not a signed-in user, so
without it the route is an open POST that could make the service hammer Gmail.

The `renew_watches` job re-arms every account daily because `watch` expires in
about seven days and then stops delivering silently.

## 7. Web app

```bash
cd apps/web && npm ci && npm run build && npm run start
```

The service worker caches nothing on purpose - a cold-outreach dashboard showing
stale "have they replied yet" is worse than one that fails to load.

## 8. Backups and restore

- **Postgres is the source of truth** - the schedule, targets, threads, and
  encrypted refresh tokens all live here. Take regular `pg_dump` backups and
  test a restore. On the self-hosted stack this is not optional and nothing
  else is doing it for you: `infra/backup-db.sh` dumps and rotates, and is
  meant to run from cron.
- Backups contain encrypted refresh tokens but **not** `MASTER_KEY`. A restore
  is only useful alongside the same `MASTER_KEY`; back that key up separately and
  never in the database.
- Redis holds only the transient job queue. Losing it drops in-flight jobs, which
  the next `tick`/`reconcile` re-derives from Postgres; no backup needed.
- `STORAGE_DIR` holds resume files only until they are parsed (deleted unless the
  user kept the original), so it is not critical to back up.
- The calendar layer is a mirror, not a backup: if events are lost, the next
  `sync_calendars` pass recreates them from the schedule.

## 9. Go-live checklist

- [ ] `GET /readyz` returns `ready: true` against production.
- [ ] `test_rls.py` passes against a copy of the production database shape.
- [ ] API connects as `outreach_app`; migrations ran as `outreach`.
- [ ] Worker process is running; `/ops` shows a recent `tick` heartbeat.
- [ ] OAuth redirect URI matches `WEB_ORIGIN`; test users added.
- [ ] Pub/Sub topic, Publisher grant, and push subscription in place; a test
      reply flips a target to `replied`.
- [ ] `MASTER_KEY` backed up somewhere other than the database.
- [ ] A `pg_dump` has been taken and a restore rehearsed.
