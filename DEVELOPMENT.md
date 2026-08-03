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

```bash
pip install -e packages/core -e apps/api
```

```bash
cd apps/api && alembic upgrade head
```

```bash
cd apps/api && uvicorn app.main:app --reload
```

```bash
cd apps/web && npm install && npm run dev
```

`GET /readyz` reports whether the database is reachable and whether the keys
that protect stored refresh tokens are actually configured.

## Google OAuth

One OAuth client (Web application), used by both apps. The consent screen stays
in **testing** mode: up to 100 users, no CASA review, and `gmail.readonly`
works from day one. Users see an "unverified app" warning; onboarding says so
before they hit it.

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

Sign-in is the exception, because it has to find a user before there is a user
to bind to. Rather than a `BYPASSRLS` role - which would exempt every query on
that connection - there is one `SECURITY DEFINER` function,
`find_user_id_by_google_sub`, that returns an id and nothing else.

## Tests

```bash
python -m unittest discover -s packages/core/tests
```

```bash
python -m unittest discover -s apps/api/tests
```
