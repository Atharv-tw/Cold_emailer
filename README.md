# Cold outreach

A website for sending personal cold email that actually gets read: sign in with
Google, upload a resume, add the people you want to reach, generate a draft,
review it, and send it through Gmail. Nothing sends until you press send or
explicitly queue a draft.

**Personal outreach only.** No marketing mode, no mailing lists, no bulk
blasts. The limits below are not a setting; they are the product.

## What it does

- **Builds the sender profile.** Upload a PDF/DOCX resume or fill the profile
  by hand. Extracted fields are suggestions and must be reviewed before saving.
- **Captures target context.** Each target has role, company, target type,
  company type, intent, links, and the specific hook that made you pick them.
- **Writes the email.** The generator combines the profile, target context,
  selected generation template, recipient playbook, and thread history.
- **Chooses relevant proof.** Profile projects can be tagged by category and
  best-fit audience so generation can prioritize the right project and link.
- **Sends properly.** Business-day scheduling, randomized times inside the
  user's sending window, warmup caps, daily caps, and correct Gmail threading.
- **Watches for replies.** Gmail push, watch renewal, and reconcile sweeps stop
  a sequence when someone replies. Out-of-office replies defer instead of
  killing the sequence.
- **Reminds about follow-ups.** Dashboard due lists and web push notifications
  surface follow-ups that need writing.

## Limits

Nobody gets hammered, including by accident.

**Per person** - at most three emails, ever. At least three business days
between them. A reply, bounce, or opt-out ends the sequence immediately and
permanently.

**Per account** - a daily cap starts low and ramps up, well under Gmail's own
limits. It is enforced server-side and there is no setting that raises it.

**Across accounts** - if the same person is being contacted by many accounts of
this platform at once, further sends are blocked for everyone. Addresses are
stored as keyed HMACs so the guard works without accumulating a readable list
of recipients.

## Your data

- Your resume text is sent to Gemini to be read. The upload screen says this
  before the file is submitted.
- The original file is deleted after parsing unless you choose to keep it.
- Google refresh tokens are encrypted at rest.
- "Delete my resume and parsed data" deletes stored resume files and parsed
  profile data.

## Layout

```text
apps/api          FastAPI. Auth, profiles, targets, generation, worker.
apps/web          Next.js. The site and PWA layer.
packages/core     Scheduling, limits, threading, reply classification.
infra             docker-compose for Postgres and Redis.
```

Setup, architecture notes, and the phased roadmap are in
[DEVELOPMENT.md](DEVELOPMENT.md).

## Current status

Built now:

- Google sign-in and Gmail token storage
- profile and resume extraction
- target creation with categorization and verification
- selectable generation templates
- project metadata for better evidence/link selection
- draft generation, editing, send-now, and scheduled sending
- threaded follow-ups with hard caps
- Gmail reply tracking through push, renewal, and reconcile sweeps
- web push and dashboard reminders for due follow-ups

Remaining phases:

1. Template/evidence control and docs alignment - in progress.
2. Target import and workflow dashboard improvements.
3. Calendar reminders and reminder sync lifecycle.
4. Analytics, polish, and production hardening.
