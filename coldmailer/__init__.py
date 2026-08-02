"""coldmailer - a cold email scheduler and sender built on real mailboxes.

Design notes that matter:

* Sends through ordinary SMTP mailboxes (Google Workspace / Microsoft 365),
  not a transactional provider. SendGrid, Resend, Mailgun and Postmark all
  ban cold outreach in their acceptable use policies.
* Volume is spread across a pool of mailboxes with per-mailbox daily caps,
  a warmup ramp, sending windows and randomised gaps.
* A contact is pinned to one mailbox for the life of its sequence so that
  follow-ups thread correctly and come from a consistent human.
* Replies, bounces and unsubscribe requests stop the sequence.
"""

__version__ = "1.0.0"
