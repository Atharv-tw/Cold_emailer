# coldmailer

A cold email scheduler and sender that runs on your own mailboxes. Drip
sequences, merge-field personalisation, per-mailbox throttling with a warmup
ramp, and automatic stop-on-reply.

No dependencies beyond PyYAML. State lives in one SQLite file.

---

## Read this before you write a single email

**The tool is the easy part. Deliverability is the whole game.** You can have
perfect copy and still land in spam if the infrastructure is wrong. Three
things matter more than anything in this repo:

**1. Do not send from a transactional provider.** SendGrid, Resend, Mailgun and
Postmark all prohibit cold outreach in their acceptable use policies — there is
no B2B carve-out. They run shared IP pools, so one bad tenant damages everyone,
and they enforce by killing accounts. This tool deliberately sends via ordinary
SMTP mailboxes instead.

**2. Do not send from your primary domain.** Buy secondary domains that
redirect to your main site (`get-yourcompany.com`, `try-yourcompany.com`). If a
sending domain gets burned, you throw it away. You cannot throw away the domain
your real email runs on.

**3. Do not exceed ~40 sends per mailbox per day.** Google's official ceiling is
2,000/day, but that limit is for mail people asked for. For cold outreach the
safe range is 20–50 per mailbox after warmup, and 10–30 for a new one. Volume
comes from *more mailboxes*, not more per mailbox.

Your target of 50–500/day therefore means roughly **2–13 mailboxes**. And note
the arithmetic that catches everyone out: follow-ups count against the cap. A
4-touch sequence at 30 sends/day is about **7 new prospects a day**, not 30.

---

## Setup

### Step 1 — Domains (day 1, ~£20/domain/year)

Buy 2–3 secondary domains. Keep them short, readable, and obviously related to
your brand. Set each to 301-redirect to your main site — a sending domain with
no website is a spam signal.

Rough plan for your volume:

| Target/day | Domains | Mailboxes | Monthly cost |
|---|---|---|---|
| 50 | 1 | 2 | ~£12 + domain |
| 150 | 2 | 4–5 | ~£30 |
| 300 | 3 | 8 | ~£48 |
| 500 | 4 | 12–13 | ~£78 |

Google Workspace Business Starter is roughly £6/user/month; each user is one
mailbox.

### Step 2 — Mailboxes (day 1)

Create a Google Workspace account on each sending domain, then 2–4 users per
domain. Use real name variants (`shivanshu@`, `s.pandey@`) — never `info@`,
`sales@`, or `hello@`, which get filtered on sight.

For each mailbox: set a profile photo, a short signature, and turn on 2FA. An
account with no photo and no history looks exactly like what it is.

### Step 3 — DNS (day 1, then wait)

On **every** sending domain, add all three records. Missing any one of them is
the single most common reason cold email fails.

```
# SPF - one TXT record on the root, and only one
@    TXT    "v=spf1 include:_spf.google.com ~all"

# DKIM - generate in Google Admin > Apps > Google Workspace > Gmail >
# Authenticate email, then publish the key it gives you
google._domainkey    TXT    "v=DKIM1; k=rsa; p=<long key from Google>"

# DMARC - start at p=none so you can read reports without blocking anything
_dmarc    TXT    "v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com; pct=100"
```

After two weeks of clean reports, tighten DMARC to `p=quarantine`.

Verify with `dig TXT yourdomain.com` and by sending one message to
[mail-tester.com](https://www.mail-tester.com). Score below 8/10 means fix the
infrastructure before sending anything real.

### Step 4 — Warmup (weeks 1–3, unskippable)

A brand-new mailbox that starts sending 40 cold emails on day one gets
filtered. The warmup ramp in `config.yaml` handles the send side automatically
(10/day, +3/day, capped at 40), but you also want genuine two-way traffic:
email colleagues, reply to those replies, subscribe to a few newsletters and
open them.

Do not start real campaigns until each mailbox is ~3 weeks old.

### Step 5 — Install and configure

```bash
pip install -r requirements.txt

cp config.example.yaml config.yaml
$EDITOR config.yaml          # identity, timezone, mailboxes
```

Passwords are never stored in the config — only the *name* of an environment
variable. For Google Workspace, generate an App Password (Google Account →
Security → App passwords; requires 2FA) and export it:

```bash
export MB1_PASSWORD='abcd efgh ijkl mnop'
export MB2_PASSWORD='...'
```

Put those in a `.env` file you source, or your shell profile. `.env` and
`config.yaml` are gitignored.

```bash
python -m coldmailer init            # create the DB, baseline the mailboxes
python -m coldmailer mailbox-test    # verify SMTP credentials
```

`init` records the current IMAP position for each mailbox so existing mail is
never mistaken for a reply.

---

## Daily use

```bash
# See what your sequence actually looks like, with spintax resolved
python -m coldmailer preview -s founders

# Load a list
python -m coldmailer import leads.csv -s founders --campaign q3-ops

# See what would go out, without sending anything
python -m coldmailer run --dry-run

# Run for real - polls for replies, then sends whatever is due
python -m coldmailer run --once

# Or leave it running; it checks every 5 minutes and respects the send window
python -m coldmailer run

python -m coldmailer stats
python -m coldmailer contacts --status replied
python -m coldmailer suppress someone@example.com --reason "asked to stop"
```

Run it unattended with cron (the tool itself enforces the window, so a
five-minute cron is fine):

```cron
*/5 * * * * cd /path/to/email && . ./.env && /usr/bin/python3 -m coldmailer run --once >> run.log 2>&1
```

On Windows, use Task Scheduler with the same command, or run
`python -m coldmailer run` in a terminal you leave open.

---

## Contact CSV

`email` is the only required column. Every other column becomes a merge field
automatically, so add whatever your copy references.

```csv
email,first_name,company,trigger,pain
dana@examplecorp.com,Dana,ExampleCorp,just opened a second warehouse,reconciling stock across three systems
```

Duplicates are ignored on re-import. Addresses on the suppression list are
skipped. Malformed addresses are counted and reported.

---

## Sequences

A sequence is a YAML file in `sequences/`. See `sequences/founders.yaml`.

```yaml
name: founders
steps:
  - id: 1
    delay_business_days: 0
    subject: "{{first_name}} - quick question about {{company}}"
    body: |
      Hi {{first_name}},
      ...
  - id: 2
    delay_business_days: 3     # no subject => replies inside the same thread
    body: |
      Following up on the note below.
```

**Template syntax**

| Syntax | Meaning |
|---|---|
| `{{first_name}}` | required merge field |
| `{{company\|your team}}` | merge field with a fallback |
| `{saw\|noticed\|spotted}` | spintax — one option picked at random |

Delays are in **business days** and count from the previous send, so a step
never lands on a Saturday. Steps without a subject reply into the original
thread with proper `In-Reply-To` and `References` headers, so Gmail and Outlook
collapse the conversation.

If a contact is missing a merge field that has no fallback, the contact is
**paused rather than sent a broken email**. Fix the CSV, then reactivate:

```sql
sqlite3 coldmailer.db "UPDATE contacts SET status='active' WHERE status='paused'"
```

---

## What stops a sequence

| Trigger | Result |
|---|---|
| Any genuine reply | status `replied`, no further sends |
| Out-of-office autoresponder | **not** a reply — deferred 7 days, then resumes |
| Hard bounce or SMTP 5xx | status `bounced`, address suppressed |
| "unsubscribe" / "remove me" in a reply | status `unsubscribed`, address suppressed |
| Address on `suppression.txt` | never contacted |
| Last step sent | status `completed` |

Reply detection matches on `In-Reply-To`/`References` against Message-IDs we
sent, and falls back to the sender address for clients that strip threading
headers.

---

## Legal

This is not legal advice, and I'm not a lawyer — but these are the mechanics
you're expected to get right.

**CAN-SPAM (US)** — commercial email must carry a working opt-out and a valid
physical postal address, must not use deceptive headers or subject lines, and
must honour opt-outs within 10 business days. The footer this tool appends
covers the address and opt-out; `config.yaml` refuses to load without both.
Penalties run to tens of thousands of dollars per email.

**GDPR (EU/UK)** — you need a lawful basis. For B2B cold outreach that is
normally *legitimate interest*, which requires the message to be relevant to
the person's professional role, an easy opt-out, and a balancing assessment you
can produce on request. Consumer addresses are a different matter — don't.
Several member states (Germany, Italy) are stricter than the baseline.

**India (DPDP Act)** — if you're sending from India to Indian recipients,
consent requirements are tighter than the B2B norms above. Check current
guidance for your situation.

**Practical rules regardless of jurisdiction:** never buy or scrape consumer
lists, honour every opt-out immediately and permanently, keep the suppression
list forever, and keep opt-out rate under 0.3% — that's Gmail's complaint
threshold, and crossing it damages the domain, not just the campaign.

---

## Layout

```
coldmailer/
  config.py       config loading, validation, warmup caps
  store.py        SQLite schema and queries
  sequences.py    sequence loading and validation
  templating.py   merge fields, spintax, footer, deliverability lint
  sender.py       SMTP transport, MIME, threading and unsubscribe headers
  scheduler.py    the tick loop - who, from where, when
  replies.py      IMAP polling for replies, bounces, autoresponders
  cli.py          command line interface
  tracker.py      optional open-tracking / one-click-unsubscribe server
tests/            35 tests, no network required
```

Run the tests with `python -m unittest discover -s tests -v`.

---

## Open tracking

Off by default, on purpose. Apple Mail Privacy Protection and Gmail's image
proxy pre-fetch tracking pixels, so a large share of recorded "opens" are
machines, and the pixel itself is a small deliverability penalty. Reply rate is
the metric that means anything.

If you still want it, run `python -m coldmailer.tracker` behind an HTTPS proxy
on a subdomain of your sending domain, then set `tracking.open_tracking: true`
and `tracking.base_url`. That also enables RFC 8058 one-click unsubscribe,
which is worth hosting on its own even if you leave pixels off.

---

## Benchmarks

For B2B cold outreach with a well-targeted list: 40–60% open rate (unreliable,
see above), **3–8% reply rate**, 1–3% positive reply rate. Under 1% reply means
the targeting or the offer is wrong — sending more will not fix it, and will
cost you a domain.
