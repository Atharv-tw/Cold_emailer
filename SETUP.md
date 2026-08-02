# Setup runbook — internship outreach

Windows / PowerShell. About 40 minutes end to end, and you can send the same
day. There is no domain to buy, no DNS to configure, and no warmup period —
your Gmail already has years of real sending history, which is worth more than
any new domain could be.

If you are instead using this for commercial marketing email, stop and read
the "Commercial use" section of `README.md`. Different rules, different risk,
and considerably more setup.

---

## Step 1 — Gmail app password (5 min)

You need an app password, not your account password.

1. Go to myaccount.google.com → Security
2. Turn on **2-Step Verification** if it isn't already
3. Search settings for **App passwords**
4. Create one named `coldmailer`
5. Copy the 16-character password — it's shown once

## Step 2 — Install (10 min)

Check Python first:

```powershell
python --version
```

3.10 or newer. If it's missing, install from python.org and tick **"Add Python
to PATH"**.

```powershell
cd $HOME\Desktop\work\email

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Step 3 — Configure (15 min)

```powershell
Copy-Item config.example.yaml config.yaml
notepad config.yaml
```

Most of your time goes into `identity.vars`. These fill every template, so you
write them once instead of in every CSV row:

| Field | Notes |
|---|---|
| `my_name`, `my_first_name` | as you want to be addressed |
| `my_status` | "a third-year CS undergrad" |
| `university` | your institution |
| `resume_url` | **a link, not an attachment** — see below |
| `portfolio` | GitHub or personal site |
| `season`, `year` | "summer", "2027" |
| `availability` | "free from May, full-time, can relocate" |
| `focus` | "ML", "applied ML", "NLP" — whatever you actually want |
| `my_project` | your strongest project, one phrase |
| `my_project_detail` | what you did and **a number** |

`my_project` and `my_project_detail` do more work than anything else in the
email. "Built a chatbot" is worth nothing. "Fine-tuned a small embedding model
that beat ada-002 by 11 points on recall@10" gets a reply. If you don't have a
number, find one — accuracy, latency, dataset size, users.

**Resume hosting.** Put the PDF somewhere with a stable link: your GitHub Pages
site, a personal domain, or Google Drive set to "anyone with the link". A link
beats an attachment — attachments from unknown senders are filtered more often,
and a Drive link tells you whether anyone actually opened it.

Also set `identity.from_name` and the mailbox `email` / `username` to your
Gmail address. Leave `footer: none` alone — that's what keeps these looking
like personal emails rather than marketing.

## Step 4 — Store the password

Never in `config.yaml`. Create `env.ps1` (already gitignored):

```powershell
@'
$env:MB1_PASSWORD = "abcd efgh ijkl mnop"
'@ | Set-Content env.ps1
```

Load it in every new terminal session:

```powershell
. .\env.ps1
```

## Step 5 — Initialize (2 min)

```powershell
python -m coldmailer init
python -m coldmailer mailbox-test
```

`mailbox-test` must print `OK`. An authentication failure means you used your
account password instead of the 16-character app password.

Then add your own domains to `suppression.txt` so you never accidentally email
yourself or a friend, and re-run `init`.

---

## Step 6 — Set your sending window

This one is easy to get wrong. The window in `config.yaml` is in **your**
timezone, but should cover your **target's** morning — 8–11am their time gets
the best response.

Sending from IST:

| Targeting | Set window (IST) |
|---|---|
| India | `09:15` – `12:00` |
| UK / Europe | `13:30` – `16:30` |
| US East | `18:30` – `21:30` |
| US West | `21:30` – `23:45` |

Pick one region per campaign rather than trying to cover all of them.

---

## Step 7 — Build the list

Four sequences ship with this, one per audience:

| Sequence | Who | Expect |
|---|---|---|
| `engineers` | people doing the work | **best reply rate** — start here |
| `founders` | CTOs at small startups | fast yes/no, often creates a role |
| `professors` | research labs | slow, high effort per email |
| `recruiters` | talent teams | lowest — expect portal redirects |

**Finding people.** Company team pages, GitHub contributors on projects you
actually use, paper author lists, conference speaker lists, LinkedIn. For
startups, the "About" page usually lists everyone.

**Finding addresses.** Most companies use a predictable pattern —
`first.last@`, `first@`, `flast@`. Find one known address for the company and
apply the pattern. Hunter.io and Clearbit have free tiers that will confirm a
guess. Verify before sending: a bounce is a wasted contact and repeated
bounces from one sender look bad to Gmail.

**The columns that matter.** `email` is required, everything else becomes a
merge field:

```csv
email,first_name,last_name,company,specific,specific_short,reaction
priya@exampleai.com,Priya,Raman,ExampleAI,your post on 4-bit quantised serving,4-bit serving,I tried reproducing the benchmark and got within 2 points
```

`specific` is the sentence that proves this isn't a blast. It must be real and
about *them* — a post they wrote, a feature they shipped, a talk they gave, a
paper they published. If you cannot write a genuine `specific` for someone,
take them off the list. That field is doing the work; everything else is
scaffolding.

The `professors` sequence additionally needs `paper`, `paper_short`, `finding`
and `question` — and those need to reflect a paper you have actually read.

**One person per company at a time.** Emailing an engineer, the CTO and a
recruiter at the same company in the same week looks exactly like what it is.

---

## Step 8 — Check the copy before importing

```powershell
python -m coldmailer preview -s engineers --csv leads.csv
```

This renders against the first real row of your list. Fix anything reported as
a missing field — those emails would be withheld rather than sent with a blank
gap. Read it out loud. If it sounds like a template, it is one.

## Step 9 — Send one to yourself

```powershell
python -m coldmailer import me.csv -s engineers --campaign test
python -m coldmailer run --once
```

Where `me.csv` contains only your own address plus realistic column values.
Check what arrives: merge fields resolved, no footer, lands in Primary rather
than Promotions, resume link works. Then:

```powershell
python -m coldmailer suppress your.other@email.com --reason "test"
```

## Step 10 — Go live

```powershell
python -m coldmailer import leads.csv -s engineers --campaign ml-internships
python -m coldmailer run --dry-run
```

Read the dry-run output. It sends nothing. When it looks right:

```powershell
python -m coldmailer run
```

Leave the terminal open. It polls for replies and sends what's due every five
minutes, inside your window, capped at 8/day rising to 20. Ctrl-C stops it.

To run without a terminal open, use Task Scheduler:

```powershell
$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -Command `". '$HOME\Desktop\work\email\env.ps1'; & '$HOME\Desktop\work\email\.venv\Scripts\python.exe' -m coldmailer run --once`"" `
  -WorkingDirectory "$HOME\Desktop\work\email"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName "coldmailer" -Action $action -Trigger $trigger
```

Remove it with `Unregister-ScheduledTask -TaskName "coldmailer" -Confirm:$false`.

---

## Daily operation

```powershell
. .\env.ps1

python -m coldmailer stats
python -m coldmailer contacts --status replied
python -m coldmailer poll
```

**When someone replies, the sequence stops automatically — then it's on you.**
Reply within a few hours. That's the entire point of the exercise; the tool
just gets you to the conversation.

## What good looks like

For a student sending well-researched emails to engineers:

| Metric | Expect |
|---|---|
| Reply rate | 10–25% — far higher than sales cold email, because you're asking for very little |
| Useful conversations | 1 in 3 replies |
| Bounces | under 2% — if higher, your address guessing is wrong |

If you're under 5% after 40 emails, the problem is the `specific` field or the
project line, not the volume. Sending 200 more of the same email will not help.
Rewrite, then send another 20.

## Common problems

**`authentication failed`.** App password, not account password. 2FA must be on.

**Contacts stuck at `paused`.** A merge field was missing, so the email was
withheld rather than sent with a hole in it. Check with
`python -m coldmailer contacts --status paused`, fix the CSV, re-import.

**Landing in Promotions.** Usually too many links or an over-formatted email.
Keep it to one link and plain text.

**Nothing sends.** Check you're inside your sending window and still have daily
capacity — `python -m coldmailer stats` shows both.

**Gmail warning about unusual activity.** Back off to 10/day for a week. You're
using your primary account; be conservative with it.
