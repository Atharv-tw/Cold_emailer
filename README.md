# Cold outreach

A website for sending personal cold email that actually gets read: sign in with
Google, upload a resume, add the people you want to reach, and the email gets
written for you. Nothing sends until you press send.

**Personal outreach only.** No marketing mode, no mailing lists, no bulk
blasts. The limits below are not a setting — they are the product.

## What it does

- **Writes the email.** You answer plain questions about a person — who they
  are, what made you pick them, what you want — and the model writes it from
  your profile. You never see a merge field.
- **Sends it properly.** Business-day scheduling, randomised times inside your
  own sending window, a warmup ramp on a new account, and correct threading so
  follow-ups land in the original conversation.
- **Watches for replies.** Three independent layers, because continuing to
  email someone who already replied is the worst thing this can do. A real
  reply stops the sequence; an out-of-office pauses it instead of killing it.
- **Installs like an app.** It is one website. On a laptop Chrome offers to
  install it; on a phone "Add to Home Screen" gives it an icon and full screen.
  Nobody has to install anything — it is an upgrade, not a requirement.

## Limits

Nobody gets hammered, including by accident.

**Per person** — at most three emails, ever. At least three business days
between them. A reply, a bounce or an opt-out ends it immediately and
permanently, and re-adding that address is refused with the reason shown.

**Per account** — a daily cap that starts low and ramps up, well under Gmail's
own limits. It is enforced server-side and there is no setting that raises it.

**Across accounts** — if the same person is being contacted by many accounts of
this platform at once, further sends to them are blocked for everyone.
Addresses are stored as a keyed HMAC, so the guard works without the platform
accumulating a record of who is being emailed.

## Your data

- Your resume is sent to Gemini to be read. You are told this at the moment you
  upload, not in a policy nobody opens.
- The original file is deleted after parsing unless you tick "keep it".
- Everything is encrypted at rest. Google refresh tokens get their own
  per-record key.
- "Delete my resume and parsed data" in settings actually deletes.

## Layout

```
apps/api          FastAPI. Auth, profiles, targets, generation, worker.
apps/web          Next.js. The site, and the PWA layer.
packages/core     Scheduling, limits, threading, reply classification.
infra             docker-compose (Postgres, Redis).
```

Setup, architecture notes and the reasoning behind the security model are in
[DEVELOPMENT.md](DEVELOPMENT.md).

## Status

Milestone 1 — skeleton and auth — is done. Sending is not wired up yet.
DEVELOPMENT.md tracks what is built and what is next.
