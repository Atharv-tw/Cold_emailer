"""Command line interface."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time as time_module
from pathlib import Path

from .config import Config, ConfigError, load_config
from .replies import poll_all
from .scheduler import remaining_capacity, schedule_step, tick
from .sender import test_connection
from .sequences import SequenceError, load_all, load_sequence
from .store import Store, parse_iso, utcnow
from .templating import contact_fields, lint, render_step

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
GREEN, YELLOW, RED, CYAN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"


def _colour(text: str, code: str) -> str:
    return text if not sys.stdout.isatty() else f"{code}{text}{RESET}"


def _load(args) -> tuple[Config, Store]:
    cfg = load_config(args.config, require_passwords=not getattr(args, "no_creds", False))
    store = Store(cfg.db_path)
    return cfg, store


def _normalise_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")


# ------------------------------------------------------------------- commands


def cmd_init(args) -> int:
    cfg, store = _load(args)
    print(f"database   {cfg.db_path}")
    added = store.load_suppression_file(cfg.suppression_file)
    if added:
        print(f"suppression {added} addresses loaded from {cfg.suppression_file.name}")

    sequences = load_all(cfg.sequences_dir)
    print(f"sequences  {len(sequences)} loaded: {', '.join(sequences) or '(none)'}")
    print(f"mailboxes  {len(cfg.active_mailboxes)} active")
    for mailbox in cfg.active_mailboxes:
        cap = remaining_capacity(cfg, store, mailbox, utcnow())
        print(f"  {mailbox.id:<8} {mailbox.email:<38} {cap} sends available today")

    print("\nSetting IMAP baselines so old mail is not treated as replies...")
    for result in poll_all(cfg, store, baseline_only=True):
        if result.error:
            print(_colour(f"  {result.mailbox_id}: {result.error}", RED))
    store.close()
    return 0


def cmd_import(args) -> int:
    cfg, store = _load(args)
    path = Path(args.csv)
    if not path.exists():
        print(_colour(f"no such file: {path}", RED))
        return 1

    sequences = load_all(cfg.sequences_dir)
    if args.sequence not in sequences:
        print(_colour(f"unknown sequence {args.sequence!r}. Available: {', '.join(sequences) or 'none'}", RED))
        return 1

    store.load_suppression_file(cfg.suppression_file)
    rng = random.Random()
    now = utcnow()
    due_at = schedule_step(now, 0, cfg, rng)

    added = skipped_dupe = skipped_bad = skipped_suppressed = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            print(_colour("CSV has no header row", RED))
            return 1
        reader.fieldnames = [_normalise_header(f) for f in reader.fieldnames]
        if "email" not in reader.fieldnames:
            print(_colour(f"CSV needs an 'email' column. Found: {reader.fieldnames}", RED))
            return 1

        for row in reader:
            address = (row.get("email") or "").strip().lower()
            if not EMAIL_RE.match(address):
                skipped_bad += 1
                continue
            if store.is_suppressed(address):
                skipped_suppressed += 1
                continue
            contact_id, created = store.upsert_contact(row, args.sequence, args.campaign or "")
            if created:
                store.set_next_due(contact_id, due_at)
                store.log_event(contact_id, "imported", path.name)
                added += 1
                # Stagger the first touch so imports don't all fire at once.
                due_at = schedule_step(now, 0, cfg, rng)
            else:
                skipped_dupe += 1

    print(_colour(f"imported {added}", GREEN))
    if skipped_dupe:
        print(f"skipped {skipped_dupe} already in the database")
    if skipped_suppressed:
        print(f"skipped {skipped_suppressed} on the suppression list")
    if skipped_bad:
        print(_colour(f"skipped {skipped_bad} with an invalid email", YELLOW))
    store.close()
    return 0


def cmd_preview(args) -> int:
    args.no_creds = True
    cfg, store = _load(args)
    sequences = load_all(cfg.sequences_dir)
    sequence = sequences.get(args.sequence)
    if sequence is None:
        print(_colour(f"unknown sequence {args.sequence!r}. Available: {', '.join(sequences) or 'none'}", RED))
        return 1

    if args.csv:
        # Render against the first row of a real list - the only way to see
        # whether your merge fields actually line up with your data.
        path = Path(args.csv)
        if not path.exists():
            print(_colour(f"no such file: {path}", RED))
            return 1
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            reader.fieldnames = [_normalise_header(f) for f in (reader.fieldnames or [])]
            row = next(reader, None)
        if row is None:
            print(_colour(f"{path} has no data rows", RED))
            return 1
        known = {"email", "first_name", "last_name", "company", "title"}
        contact_data = {
            "email": row.get("email", ""), "custom": json.dumps(
                {k: v for k, v in row.items() if k not in known and v}
            ),
            "unsub_token": "preview", "campaign": "preview",
            **{k: row.get(k, "") for k in known if k != "email"},
        }
        print(_colour(f"rendering against {row.get('email', '?')} from {path.name}", DIM))
    elif args.email:
        contact = store.find_contact_by_email(args.email)
        if contact is None:
            print(_colour(f"no contact {args.email}", RED))
            return 1
        contact_data = dict(contact)
    else:
        contact_data = {
            "email": "dana@examplecorp.com", "first_name": "Dana", "last_name": "Okafor",
            "company": "ExampleCorp", "title": "Head of Ops", "custom": "{}",
            "unsub_token": "preview", "campaign": "preview",
        }

    rng = random.Random(args.seed)
    thread_subject = None
    for step in sequence.steps:
        rendered = render_step(
            {"id": step.id, "subject": step.subject, "body": step.body},
            contact_data, cfg.identity, thread_subject=thread_subject, rng=rng,
        )
        thread_subject = thread_subject or rendered.subject
        delay = "immediately" if step.delay_business_days == 0 else f"+{step.delay_business_days} business days"
        print(_colour(f"\n─── step {step.id} ({delay}) ───", CYAN))
        print(_colour("Subject: ", BOLD) + rendered.subject)
        print()
        print(rendered.body)
        if rendered.missing:
            print(_colour(f"\n  MISSING FIELDS: {', '.join(rendered.missing)}", RED))
        for warning in lint(rendered.body):
            print(_colour(f"  lint: {warning}", YELLOW))

    store.close()
    return 0


def cmd_run(args) -> int:
    cfg, store = _load(args)
    sequences = load_all(cfg.sequences_dir)
    if not sequences:
        print(_colour(f"no sequences found in {cfg.sequences_dir}", RED))
        return 1

    def once() -> None:
        if not args.no_poll and not args.dry_run:
            for result in poll_all(cfg, store):
                if result.error:
                    print(_colour(f"  poll {result.mailbox_id}: {result.error}", RED))
                elif result.scanned:
                    print(
                        f"  poll {result.mailbox_id}: {result.scanned} new, "
                        f"{result.replies} replies, {result.bounces} bounces, "
                        f"{result.unsubscribes} opt-outs, {result.autoreplies} auto"
                    )

        results = tick(cfg, store, sequences, dry_run=args.dry_run)
        for r in results:
            colour = {"sent": GREEN, "dry-run": CYAN, "failed": RED}.get(r.outcome, YELLOW)
            print(
                _colour(f"  {r.outcome:<8}", colour)
                + f" {r.email:<34} step {r.step} "
                + _colour(f"[{r.mailbox_id}]", DIM)
                + (f" {r.detail}" if r.detail else "")
            )
        if not results:
            in_window = cfg.sending.is_sending_time(utcnow())
            print(_colour("  nothing due" if in_window else "  outside sending window", DIM))

    if args.once or args.dry_run:
        once()
    else:
        interval = max(30, args.interval)
        print(f"running every {interval}s - ctrl-c to stop")
        try:
            while True:
                print(_colour(f"\n[{utcnow().astimezone(cfg.sending.tz):%Y-%m-%d %H:%M:%S %Z}]", DIM))
                once()
                time_module.sleep(interval)
        except KeyboardInterrupt:
            print("\nstopped")

    store.close()
    return 0


def cmd_poll(args) -> int:
    cfg, store = _load(args)
    for result in poll_all(cfg, store):
        if result.error:
            print(_colour(f"{result.mailbox_id}: {result.error}", RED))
        else:
            print(
                f"{result.mailbox_id}: scanned {result.scanned}, replies {result.replies}, "
                f"bounces {result.bounces}, opt-outs {result.unsubscribes}, auto {result.autoreplies}"
            )
    store.close()
    return 0


def cmd_stats(args) -> int:
    args.no_creds = True
    cfg, store = _load(args)
    data = store.stats()

    print(_colour("contacts", BOLD))
    total = sum(data["contacts"].values()) or 1
    for status, count in sorted(data["contacts"].items(), key=lambda kv: -kv[1]):
        print(f"  {status:<14} {count:>6}  {count / total:>6.1%}")

    sent = data["sent"] or 1
    print(_colour("\ndelivery", BOLD))
    print(f"  sent           {data['sent']:>6}")
    print(f"  failed         {data['failed']:>6}")
    print(f"  bounces        {data['bounces']:>6}  {data['bounces'] / sent:>6.1%}")
    print(_colour("\nengagement", BOLD))
    print(f"  replies        {data['replies']:>6}  {data['replies'] / sent:>6.1%}")
    print(f"  unsubscribes   {data['unsubscribes']:>6}  {data['unsubscribes'] / sent:>6.1%}")
    if cfg.tracking.open_tracking:
        print(f"  opens          {data['opens']:>6}  {data['opens'] / sent:>6.1%}")

    # Rates are meaningless below a sane sample size, and alarming for no reason.
    if data["sent"] >= 50:
        if data["unsubscribes"] / sent > 0.003:
            print(_colour("\n  opt-out rate is above 0.3% - Gmail's threshold. Tighten targeting.", RED))
        if data["bounces"] / sent > 0.03:
            print(_colour("  bounce rate above 3% - verify your list before sending more.", RED))

    print(_colour("\ntoday by mailbox", BOLD))
    for mailbox in cfg.active_mailboxes:
        used = data["per_mailbox_today"].get(mailbox.id, 0)
        left = remaining_capacity(cfg, store, mailbox, utcnow())
        print(f"  {mailbox.id:<8} {mailbox.email:<34} sent {used:>3}, {left:>3} left")
    store.close()
    return 0


def cmd_mailbox_test(args) -> int:
    cfg, store = _load(args)
    failures = 0
    for mailbox in cfg.mailboxes:
        ok, message = test_connection(mailbox)
        marker = _colour("OK  ", GREEN) if ok else _colour("FAIL", RED)
        print(f"{marker} {mailbox.id:<8} {mailbox.email:<34} {message}")
        failures += 0 if ok else 1
    store.close()
    return 1 if failures else 0


def cmd_suppress(args) -> int:
    args.no_creds = True
    cfg, store = _load(args)
    for address in args.emails:
        store.suppress(address, reason=args.reason)
        contact = store.find_contact_by_email(address)
        if contact:
            store.set_contact_status(int(contact["id"]), "unsubscribed", args.reason or "manual")
        print(f"suppressed {address.lower()}")
    store.close()
    return 0


def cmd_contacts(args) -> int:
    args.no_creds = True
    cfg, store = _load(args)
    query = "SELECT * FROM contacts"
    params: tuple = ()
    if args.status:
        query += " WHERE status = ?"
        params = (args.status,)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params += (args.limit,)

    rows = store.conn.execute(query, params).fetchall()
    tz_label = cfg.sending.timezone
    print(f"{'email':<36}{'status':<14}{'seq':<14}{'step':<6}next due ({tz_label})")
    for row in rows:
        due_utc = parse_iso(row["next_due_at"])
        due = f"{due_utc.astimezone(cfg.sending.tz):%Y-%m-%d %H:%M}" if due_utc else "-"
        print(f"{row['email']:<36}{row['status']:<14}{row['sequence']:<14}{row['next_step']:<6}{due}")
    print(_colour(f"\n{len(rows)} shown", DIM))
    store.close()
    return 0


# ---------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coldmailer", description="Cold email scheduler and sender."
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="path to config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="create the database and set IMAP baselines").set_defaults(func=cmd_init)

    p = subparsers.add_parser("import", help="load contacts from a CSV")
    p.add_argument("csv")
    p.add_argument("-s", "--sequence", required=True)
    p.add_argument("--campaign", default="")
    p.set_defaults(func=cmd_import)

    p = subparsers.add_parser("preview", help="render a sequence without sending")
    p.add_argument("-s", "--sequence", required=True)
    p.add_argument("-e", "--email", help="render against a contact already imported")
    p.add_argument("--csv", help="render against the first row of a CSV, before importing")
    p.add_argument("--seed", type=int, default=None, help="fix the spintax RNG")
    p.set_defaults(func=cmd_preview)

    p = subparsers.add_parser("run", help="poll for replies then send whatever is due")
    p.add_argument("--once", action="store_true", help="one pass instead of looping")
    p.add_argument("--dry-run", action="store_true", help="show what would send; sends nothing")
    p.add_argument("--no-poll", action="store_true", help="skip IMAP reply checking")
    p.add_argument("--interval", type=int, default=300, help="seconds between passes")
    p.set_defaults(func=cmd_run)

    subparsers.add_parser("poll", help="check mailboxes for replies and bounces").set_defaults(func=cmd_poll)
    subparsers.add_parser("stats", help="campaign numbers").set_defaults(func=cmd_stats)
    subparsers.add_parser("mailbox-test", help="verify SMTP credentials").set_defaults(func=cmd_mailbox_test)

    p = subparsers.add_parser("suppress", help="never email these addresses again")
    p.add_argument("emails", nargs="+")
    p.add_argument("--reason", default="manual")
    p.set_defaults(func=cmd_suppress)

    p = subparsers.add_parser("contacts", help="list contacts")
    p.add_argument("--status", help="filter: active, replied, bounced, unsubscribed, completed, paused")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_contacts)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, SequenceError) as exc:
        print(_colour(f"\n{exc}\n", RED), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
