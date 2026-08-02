# coldmailer

A cold email scheduler and sender that runs on your own mailbox. Drip
sequences, merge-field personalisation, throttling, and automatic stop-on-reply.

Built for internship and research outreach — sending a small number of
genuinely personalised emails from a personal Gmail, and never emailing someone
again once they answer.

No dependencies beyond PyYAML. State lives in one SQLite file.

**→ [SETUP.md](SETUP.md) is the step-by-step. Start there.**

---

## What it does

- **Sequences.** Two or three touches, spaced in business days, follow-ups
  replying inside the original thread rather than arriving as new emails.
- **Personalisation.** Merge fields from a CSV, plus config-level variables so
  you write your resume link and availability once, not per row.
- **Stops when it should.** A reply, a bounce, or an "unsubscribe" ends the
  sequence. Out-of-office autoresponders don't — they defer a week.
- **Throttling.** Daily caps with a ramp, a sending window, and randomised gaps
  between sends.
- **Won't send broken mail.** A contact missing a merge field is paused, not
  emailed with a blank where their company name should be.

## Quick reference

```bash
python -m coldmailer init                             # create DB, baseline IMAP
python -m coldmailer mailbox-test                     # verify credentials
python -m coldmailer preview -s engineers --csv leads.csv   # check copy first
python -m coldmailer import leads.csv -s engineers    # load a list
python -m coldmailer run --dry-run                    # show, don't send
python -m coldmailer run                              # go
python -m coldmailer stats
python -m coldmailer contacts --status replied
python -m coldmailer suppress someone@example.com
```

## Sequences

Four ship with this, one per audience — see the `description` at the top of
each file in `sequences/` for who it's for and what to expect.

| File | Audience | Touches |
|---|---|---|
| `engineers.yaml` | people doing the work you want to do | 2 |
| `founders.yaml` | CTOs and founders at small startups | 3 |
| `professors.yaml` | research groups | 2 |
| `recruiters.yaml` | talent teams | 2 |

**Template syntax**

| Syntax | Meaning |
|---|---|
| `{{first_name}}` | required merge field |
| `{{company\|your team}}` | merge field with a fallback |
| `{saw\|noticed\|spotted}` | spintax — one option picked at random |

Values from `identity.vars` in the config are available everywhere; a CSV
column of the same name overrides them.

Delays are in **business days** from the previous send, so a follow-up never
lands on a Saturday. A step with no `subject` replies into the existing thread
with proper `In-Reply-To` and `References` headers.

Write body paragraphs as single long lines. The mail client wraps them to the
reader's window; hard-wrapping produces ragged text once merge fields expand.

## What stops a sequence

| Trigger | Result |
|---|---|
| Any genuine reply | status `replied`, no further sends |
| Out-of-office autoresponder | **not** a reply — deferred 7 days, then resumes |
| Hard bounce or SMTP 5xx | status `bounced`, address suppressed |
| "unsubscribe" / "remove me" in a reply | status `unsubscribed`, address suppressed |
| Address in `suppression.txt` | never contacted |
| Last step sent | status `completed` |

Reply detection matches `In-Reply-To`/`References` against Message-IDs we sent,
falling back to the sender address for clients that strip threading headers.

---

## Personal outreach vs commercial email

These are different activities with different rules, and the config makes you
choose. `identity.footer` is the switch.

**`footer: none` — personal outreach.** Job applications, research enquiries,
asking a stranger a question. Not advertising a product, so CAN-SPAM's postal
address and opt-out requirements don't apply. No compliance block is appended
and no `List-Unsubscribe` header is set — adding either would make a personal
note read as a mass mailing and cost you replies. This is the default in the
shipped config.

**`footer: full` — commercial marketing.** Appends a postal address and opt-out
line, and sets unsubscribe headers. The config refuses to load without both
fields. If you send marketing mail without them, CAN-SPAM penalties run to tens
of thousands of dollars per email.

There's a `minimal` setting between the two: a polite opt-out line, no address.

Either way: honour every opt-out immediately and permanently, never buy or
scrape consumer lists, and keep the suppression list forever. Under GDPR, B2B
outreach normally relies on *legitimate interest*, which requires the message
to be genuinely relevant to the person's professional role.

I'm not a lawyer and this isn't legal advice.

---

## Commercial use

If you do point this at marketing rather than personal outreach, three things
change, and the cost is real:

**Don't use a transactional provider.** SendGrid, Resend, Mailgun and Postmark
all prohibit cold outreach in their acceptable use policies — there's no B2B
carve-out. They run shared IP pools and enforce by killing accounts.

**Don't use your primary domain.** Buy secondary domains that redirect to your
main site. A burned sending domain is disposable; your real one isn't.

**Don't exceed ~40 sends per mailbox per day.** Google's ceiling is 2,000/day,
but that's for mail people asked for. Cold volume comes from *more mailboxes*,
each with SPF, DKIM and DMARC configured and three weeks of warmup. And
follow-ups count against the cap — a 3-touch sequence at 30/day is about 10 new
prospects a day, not 30.

Set `footer: full`, add the mailboxes to `config.yaml`, and raise `max_cap`
no higher than 40.

---

## Layout

```
coldmailer/
  config.py       config loading, validation, footer modes, warmup caps
  store.py        SQLite schema and queries
  sequences.py    sequence loading and validation
  templating.py   merge fields, spintax, footer, deliverability lint
  sender.py       SMTP transport, MIME, threading headers
  scheduler.py    the tick loop — who, from where, when
  replies.py      IMAP polling for replies, bounces, autoresponders
  cli.py          command line interface
  tracker.py      optional open-tracking / one-click-unsubscribe server
tests/            40 tests, no network required
```

```bash
python -m unittest discover -s tests -v
```

## Open tracking

Off by default, and worth leaving off for personal outreach — a tracking pixel
in a job application is both unreliable and slightly grubby if noticed. Apple
Mail Privacy Protection and Gmail's image proxy pre-fetch pixels anyway, so a
large share of recorded "opens" are machines.

If you need it for commercial sending, run `python -m coldmailer.tracker`
behind an HTTPS proxy and set `tracking.open_tracking` and `tracking.base_url`.
That also enables RFC 8058 one-click unsubscribe.
