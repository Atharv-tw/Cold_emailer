# Setup runbook

Windows / PowerShell. Follow in order — the waiting periods are not optional,
and skipping them is the most common way this fails.

Total hands-on time is about 90 minutes, spread over three weeks of DNS
propagation and mailbox warmup.

---

## Timeline at a glance

| When | What | Hands-on |
|---|---|---|
| Day 1 | Buy domains, create mailboxes, publish DNS | ~60 min |
| Day 1 | Install and configure the tool | ~20 min |
| Days 2–21 | Warmup: light manual sending, no campaigns | 5 min/day |
| Day 8 | Verify DNS and inbox placement | ~10 min |
| Day 22 | First real campaign | — |

---

# Part 1 — Infrastructure (day 1)

## Step 1. Buy sending domains

Buy 2 domains from any registrar (Namecheap, Cloudflare, Porkbun). Do **not**
use the domain your real email runs on.

Pick variants of your brand:

```
get-yourcompany.com
try-yourcompany.com
```

Set each to 301-redirect to your main website. A sending domain that resolves
to nothing is a spam signal.

**Checkpoint:** visiting `get-yourcompany.com` lands on your real site.

## Step 2. Create Google Workspace mailboxes

1. Go to workspace.google.com, start a Business Starter plan on the first
   sending domain (~£6/user/month).
2. Verify domain ownership with the TXT record Google gives you.
3. Create 2 users per domain, using real name variants:

```
shivanshu@get-yourcompany.com
s.pandey@get-yourcompany.com
```

Never `info@`, `sales@`, `hello@`, or `noreply@` — those get filtered on sight.

4. For each mailbox: log in once, set a profile photo, write a short
   signature, and **turn on 2-Step Verification** (required for app passwords
   in the next part).

Repeat for the second domain.

**Checkpoint:** you can log into each mailbox and send a normal email.

## Step 3. Publish DNS records

On **every** sending domain, add all three records. Missing any one is the
number one reason cold email lands in spam.

**SPF** — one TXT record on the root. If you already have an SPF record, merge
into it rather than adding a second; two SPF records is worse than none.

```
Type: TXT    Host: @    Value: v=spf1 include:_spf.google.com ~all
```

**DKIM** — generate the key first: Google Admin → Apps → Google Workspace →
Gmail → Authenticate email → Generate new record (choose 2048-bit).

```
Type: TXT    Host: google._domainkey    Value: v=DKIM1; k=rsa; p=<key Google gives you>
```

Then click **Start authentication** in the Admin console.

**DMARC** — start permissive so you get reports without blocking anything.

```
Type: TXT    Host: _dmarc    Value: v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com; pct=100
```

**Checkpoint** — wait 30 minutes, then in PowerShell:

```powershell
Resolve-DnsName -Type TXT get-yourcompany.com
Resolve-DnsName -Type TXT google._domainkey.get-yourcompany.com
Resolve-DnsName -Type TXT _dmarc.get-yourcompany.com
```

All three must return the values you set. DNS can take up to 48 hours — do not
proceed to real sending until they resolve.

## Step 4. Generate app passwords

For each mailbox, logged in as that user:

1. Go to myaccount.google.com → Security → 2-Step Verification → App passwords
2. Create one named `coldmailer`
3. Copy the 16-character password (shown once)

Keep them somewhere safe for the next step.

---

# Part 2 — Install the tool (day 1)

## Step 5. Check Python

```powershell
python --version
```

Needs 3.10 or newer. If missing, install from python.org and tick
**"Add Python to PATH"** during install.

## Step 6. Create a virtual environment

```powershell
cd $HOME\Desktop\work\email

python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Your prompt should now show `(.venv)`.

```powershell
pip install -r requirements.txt
```

## Step 7. Configure

```powershell
Copy-Item config.example.yaml config.yaml
notepad config.yaml
```

Edit these, at minimum:

| Field | Notes |
|---|---|
| `identity.from_name` | your real name |
| `identity.company` | your company |
| `identity.physical_address` | **real postal address — legally required** |
| `identity.unsubscribe_mailto` | a mailbox you actually read |
| `sending.timezone` | `Asia/Kolkata` for IST |
| `mailboxes[].email` | your new sending addresses |
| `mailboxes[].username` | same as email |

Leave `warmup` alone. The defaults are the safe ones.

## Step 8. Store the app passwords

Passwords never go in `config.yaml`. Create `env.ps1` in the project folder —
it is gitignored:

```powershell
@'
$env:MB1_PASSWORD = "abcd efgh ijkl mnop"
$env:MB2_PASSWORD = "qrst uvwx yzab cdef"
'@ | Set-Content env.ps1
```

Load it in every new terminal session before running the tool:

```powershell
. .\env.ps1
```

## Step 9. Initialize

```powershell
python -m coldmailer init
```

This creates `coldmailer.db`, loads the suppression list, and records the
current IMAP position for each mailbox so existing mail is never mistaken for
a reply.

```powershell
python -m coldmailer mailbox-test
```

Every mailbox must print `OK`. If you see an authentication failure, you used
your account password instead of the 16-character app password, or 2FA is off.

**Checkpoint:** `init` and `mailbox-test` both clean.

## Step 10. Seed the suppression list

Add your own domains so you never cold-email yourself, a colleague, or an
existing customer:

```powershell
notepad suppression.txt
```

```
yourcompany.com
gmail.com-addresses-of-your-team@example.com
```

Then re-run `python -m coldmailer init` to load them.

---

# Part 3 — Warmup (days 2–21)

**Do not run campaigns during this window.** A three-week-old mailbox that
starts at 10/day and ramps gets delivered. A day-old mailbox sending 40 gets
filtered, and you lose the domain.

Each day, from each mailbox, by hand:

- Send 2–3 real emails to colleagues and reply to their replies
- Subscribe to a couple of newsletters and actually open them
- Move anything that lands in spam to the inbox

The tool's warmup ramp handles the automated side once you start (10/day,
+3/day, capped at 40) — this part is about giving the mailbox genuine two-way
history.

## Day 8 checkpoint — verify inbox placement

Send one email from each mailbox to the address shown at
[mail-tester.com](https://www.mail-tester.com).

**Score 8/10 or better before proceeding.** Below that, the report tells you
exactly which record is wrong. Fix it and retest — do not start sending on a
low score.

---

# Part 4 — First campaign (day 22)

## Step 11. Write the sequence

```powershell
Copy-Item sequences\founders.yaml sequences\mycampaign.yaml
notepad sequences\mycampaign.yaml
```

Rules that matter more than the wording:

- Under 90 words per email
- One question, one ask
- At most one link, ideally zero on the first touch
- Steps 2+ have **no subject line** — they reply into the same thread
- Reference something specific about them, not about you

Preview it with spintax resolved:

```powershell
python -m coldmailer preview -s mycampaign
```

Fix anything flagged as a lint warning or a missing field.

## Step 12. Build the contact list

`email` is the only required column. Every other column becomes a merge field.

```csv
email,first_name,company,trigger,pain
dana@examplecorp.com,Dana,ExampleCorp,just opened a second warehouse,reconciling stock across three systems
```

Verify the addresses first with a service like NeverBounce or ZeroBounce. A
bounce rate above 3% damages the domain — list hygiene is cheaper than a
burned domain.

## Step 13. Test on yourself first

```powershell
python -m coldmailer import test-list.csv -s mycampaign --campaign smoke-test
python -m coldmailer run --once
```

Use a CSV containing only your own personal address. Check the email that
arrives: merge fields resolved, footer present, lands in Primary not Promotions.

Then clear it:

```powershell
python -m coldmailer suppress your.personal@gmail.com --reason "test"
```

## Step 14. Go live

```powershell
python -m coldmailer import leads.csv -s mycampaign --campaign q3-ops
python -m coldmailer run --dry-run
```

Read the dry-run output carefully. It sends nothing. When it looks right:

```powershell
python -m coldmailer run
```

Leave that terminal open. It polls for replies and sends whatever is due,
every 5 minutes, respecting the sending window. Ctrl-C to stop.

## Step 15. Run it unattended

To have it run without a terminal open, use Task Scheduler:

```powershell
$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -Command `". '$HOME\Desktop\work\email\env.ps1'; & '$HOME\Desktop\work\email\.venv\Scripts\python.exe' -m coldmailer run --once`"" `
  -WorkingDirectory "$HOME\Desktop\work\email"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName "coldmailer" -Action $action -Trigger $trigger
```

The tool enforces the sending window itself, so a five-minute trigger running
all day is fine — it simply does nothing outside working hours.

To stop it:

```powershell
Unregister-ScheduledTask -TaskName "coldmailer" -Confirm:$false
```

---

# Daily operation

```powershell
. .\env.ps1                                    # once per terminal session

python -m coldmailer stats                     # how the campaign is doing
python -m coldmailer contacts --status replied # who answered
python -m coldmailer poll                      # force a reply check
python -m coldmailer suppress a@b.com          # never contact again
```

## What to watch

| Metric | Healthy | Act if |
|---|---|---|
| Reply rate | 3–8% | under 1% — targeting or offer is wrong, not volume |
| Bounce rate | under 2% | over 3% — stop, verify the list |
| Opt-out rate | under 0.3% | over 0.3% — Gmail's threshold, tighten targeting |

Under 1% reply rate means sending more will not help and will cost you a
domain. Fix the list or the offer instead.

## Common problems

**Everything lands in spam.** Check mail-tester score. Usually a missing DKIM
record or a mailbox pushed too hard too early.

**`authentication failed`.** App password, not account password. 2FA must be on.

**Contacts stuck at `paused`.** A merge field was missing, so the email was
withheld rather than sent broken. Fix the CSV, then:

```powershell
python -m coldmailer contacts --status paused
```

Re-import the corrected rows after deleting the paused ones, or reactivate
directly:

```powershell
sqlite3 coldmailer.db "UPDATE contacts SET status='active' WHERE status='paused'"
```

**Nothing sends.** Check you are inside the sending window and that the mailbox
still has daily capacity — `python -m coldmailer stats` shows both.
