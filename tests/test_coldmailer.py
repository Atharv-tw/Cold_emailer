"""End-to-end tests. Run with:  python -m unittest discover -s tests -v

SMTP is replaced with a fake transport that records every message, so the
tests exercise the real MIME construction, threading headers, quota logic,
gap enforcement and sequence state machine without touching the network.
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coldmailer import scheduler, sender  # noqa: E402
from coldmailer.config import ConfigError, load_config  # noqa: E402
from coldmailer.scheduler import (  # noqa: E402
    remaining_capacity, schedule_step, tick,
)
from coldmailer.sequences import SequenceError, load_all, load_sequence  # noqa: E402
from coldmailer.store import Store, utcnow  # noqa: E402
from coldmailer.templating import (  # noqa: E402
    contact_fields, expand_spintax, lint, render, render_step,
)

IST = ZoneInfo("Asia/Kolkata")

CONFIG_YAML = """
identity:
  from_name: "Test Sender"
  company: "TestCo"
  physical_address: "1 Test Lane, Bengaluru 560001"
  unsubscribe_mailto: "unsub@test.example"

sending:
  timezone: "Asia/Kolkata"
  window_start: "09:00"
  window_end: "17:00"
  days: [mon, tue, wed, thu, fri]
  min_gap_seconds: 60
  max_gap_seconds: 60
  max_per_tick: 50

warmup:
  enabled: true
  start_cap: 3
  increment_per_day: 2
  max_cap: 10

mailboxes:
  - id: mb1
    email: "a@send.test"
    password_env: TEST_MB1
    daily_cap: 10
  - id: mb2
    email: "b@send.test"
    password_env: TEST_MB2
    daily_cap: 10
"""

SEQUENCE_YAML = """
name: test
steps:
  - id: 1
    delay_business_days: 0
    subject: "Hi {{first_name}} - about {{company}}"
    body: |
      Hi {{first_name}},
      A note about {{company}}.
  - id: 2
    delay_business_days: 3
    body: |
      Following up, {{first_name}}.
  - id: 3
    delay_business_days: 5
    body: |
      Last one, {{first_name}}.
"""


class FakeSMTP:
    """Stands in for coldmailer.sender.send. Records what would go out."""

    def __init__(self):
        self.sent: list = []
        self.fail_with: Exception | None = None

    def __call__(self, cfg, mailbox, out):
        if self.fail_with is not None:
            raise self.fail_with
        msg = sender.build_message(cfg, mailbox, out)
        self.sent.append((mailbox.id, out.to_email, msg))
        return msg["Message-ID"]

    @property
    def recipients(self) -> list[str]:
        return [to for _, to, _ in self.sent]


class Base(unittest.TestCase):
    def setUp(self):
        os.environ["TEST_MB1"] = "pw1"
        os.environ["TEST_MB2"] = "pw2"

        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "sequences").mkdir()
        (root / "config.yaml").write_text(CONFIG_YAML, encoding="utf-8")
        (root / "sequences" / "test.yaml").write_text(SEQUENCE_YAML, encoding="utf-8")

        self.root = root
        self.cfg = load_config(root / "config.yaml")
        self.store = Store(self.cfg.db_path)
        self.sequences = load_all(self.cfg.sequences_dir)

        self.fake = FakeSMTP()
        self._real_send = scheduler.send
        scheduler.send = self.fake

        # Monday 2026-08-03, 10:00 IST - inside the sending window.
        self.now = datetime(2026, 8, 3, 10, 0, tzinfo=IST).astimezone(timezone.utc)
        self.rng = random.Random(1234)

    def tearDown(self):
        scheduler.send = self._real_send
        self.store.close()
        self.tmp.cleanup()

    def add_contact(self, email="dana@example.com", **extra):
        row = {"email": email, "first_name": "Dana", "company": "ExampleCorp", **extra}
        contact_id, _ = self.store.upsert_contact(row, "test")
        self.store.set_next_due(contact_id, self.now)
        return contact_id

    def run_tick(self, when=None, **kwargs):
        return tick(
            self.cfg, self.store, self.sequences,
            now=when or self.now, rng=self.rng, log=lambda _: None, **kwargs,
        )


# --------------------------------------------------------------- templating


class TestTemplating(Base):
    def test_merge_fields_and_fallback(self):
        out = render("Hi {{first_name}} at {{company|your team}}", {"first_name": "Dana"})
        self.assertEqual(out, "Hi Dana at your team")

    def test_missing_field_is_reported(self):
        missing: list[str] = []
        render("Hi {{first_name}}, re {{trigger}}", {"first_name": "Dana"}, missing=missing)
        self.assertEqual(missing, ["trigger"])

    def test_spintax_picks_one_option(self):
        for _ in range(20):
            self.assertIn(expand_spintax("{saw|noticed|spotted}"), {"saw", "noticed", "spotted"})

    def test_merge_values_are_not_respun(self):
        # A value containing pipes inside braces must survive verbatim.
        out = render("{{note}}", {"note": "{a|b}"})
        self.assertEqual(out, "{a|b}")

    def test_footer_carries_address_and_optout(self):
        rendered = render_step(
            {"id": 1, "subject": "Hi {{first_name}}", "body": "Body"},
            {"email": "d@e.com", "first_name": "Dana", "custom": "{}", "unsub_token": "t"},
            self.cfg.identity,
        )
        self.assertIn("1 Test Lane", rendered.body)
        self.assertIn("unsubscribe", rendered.body.lower())

    def test_followup_subject_becomes_re(self):
        rendered = render_step(
            {"id": 2, "subject": None, "body": "Following up"},
            {"email": "d@e.com", "first_name": "Dana", "custom": "{}", "unsub_token": "t"},
            self.cfg.identity,
            thread_subject="Hi Dana - about ExampleCorp",
        )
        self.assertEqual(rendered.subject, "Re: Hi Dana - about ExampleCorp")

    def test_footer_none_appends_nothing(self):
        path = self.root / "personal.yaml"
        path.write_text(
            CONFIG_YAML.replace(
                'from_name: "Test Sender"',
                'from_name: "Test Sender"\n  footer: none',
            ),
            encoding="utf-8",
        )
        cfg = load_config(path)
        rendered = render_step(
            {"id": 1, "subject": "Hi", "body": "Body text"},
            {"email": "d@e.com", "first_name": "Dana", "custom": "{}", "unsub_token": "t"},
            cfg.identity,
        )
        self.assertEqual(rendered.body, "Body text")
        self.assertNotIn("unsubscribe", rendered.body.lower())

    def test_personal_mail_omits_list_unsubscribe_header(self):
        path = self.root / "personal2.yaml"
        path.write_text(
            CONFIG_YAML.replace(
                'from_name: "Test Sender"',
                'from_name: "Test Sender"\n  footer: none',
            ),
            encoding="utf-8",
        )
        cfg = load_config(path)
        msg = sender.build_message(
            cfg, cfg.mailboxes[0],
            sender.Outgoing(to_email="d@e.com", subject="Hi", body="Body"),
        )
        self.assertIsNone(msg.get("List-Unsubscribe"))

    def test_config_vars_fill_templates(self):
        path = self.root / "vars.yaml"
        path.write_text(
            CONFIG_YAML.replace(
                'from_name: "Test Sender"',
                'from_name: "Test Sender"\n  vars:\n    resume_url: "https://me.dev/cv.pdf"',
            ),
            encoding="utf-8",
        )
        cfg = load_config(path)
        rendered = render_step(
            {"id": 1, "subject": "Hi", "body": "CV: {{resume_url}}"},
            {"email": "d@e.com", "first_name": "Dana", "custom": "{}", "unsub_token": "t"},
            cfg.identity,
        )
        self.assertIn("https://me.dev/cv.pdf", rendered.body)
        self.assertTrue(rendered.ok)

    def test_csv_column_overrides_config_var(self):
        fields = contact_fields(
            {"email": "d@e.com", "custom": '{"focus": "computer vision"}'},
            {"focus": "ML"},
        )
        self.assertEqual(fields["focus"], "computer vision")

    def test_tech_acronyms_do_not_trip_the_caps_check(self):
        self.assertEqual(lint("I fine-tuned BERT with CUDA and PyTorch."), [])
        self.assertIn("ALL-CAPS", " ".join(lint("THIS IS URGENT")))

    def test_lint_flags_spam_triggers_and_links(self):
        warnings = lint("ACT NOW click here https://a.com https://b.com FREE!!")
        joined = " ".join(warnings)
        self.assertIn("spam trigger", joined)
        self.assertIn("links", joined)


# ----------------------------------------------------------------- sequences


class TestSequences(Base):
    def test_valid_sequence_loads(self):
        sequence = load_sequence(self.root / "sequences" / "test.yaml")
        self.assertEqual(sequence.last_step_id, 3)
        self.assertTrue(sequence.step(2).is_followup)

    def test_step_one_needs_a_subject(self):
        path = self.root / "sequences" / "bad.yaml"
        path.write_text("name: bad\nsteps:\n  - id: 1\n    body: hi\n", encoding="utf-8")
        with self.assertRaises(SequenceError):
            load_sequence(path)

    def test_empty_body_rejected(self):
        path = self.root / "sequences" / "bad2.yaml"
        path.write_text("name: bad2\nsteps:\n  - id: 1\n    subject: x\n    body: '  '\n", encoding="utf-8")
        with self.assertRaises(SequenceError):
            load_sequence(path)


# ------------------------------------------------------------------- config


class TestConfig(Base):
    def test_missing_physical_address_is_rejected(self):
        path = self.root / "bad.yaml"
        path.write_text(
            'identity:\n  from_name: X\n  unsubscribe_mailto: u@x.com\n'
            'mailboxes:\n  - id: m\n    email: a@b.com\n    password_env: TEST_MB1\n',
            encoding="utf-8",
        )
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("physical_address", str(ctx.exception))

    def test_password_must_come_from_env(self):
        path = self.root / "bad2.yaml"
        path.write_text(
            'identity:\n  from_name: X\n  physical_address: Y\n  unsubscribe_mailto: u@x.com\n'
            'mailboxes:\n  - id: m\n    email: a@b.com\n    password: hunter2\n',
            encoding="utf-8",
        )
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("password_env", str(ctx.exception))

    def test_unknown_timezone_reports_a_typo(self):
        path = self.root / "tz.yaml"
        path.write_text(
            CONFIG_YAML.replace('timezone: "Asia/Kolkata"', 'timezone: "Asia/Delhi"'),
            encoding="utf-8",
        )
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("Unknown timezone", str(ctx.exception))

    def test_missing_tzdata_says_how_to_fix_it(self):
        """Windows ships no IANA database - the error must not look like a typo."""
        import builtins
        import zoneinfo
        from unittest import mock

        from coldmailer import config as config_module

        real_import = builtins.__import__

        def no_tzdata(name, *args, **kwargs):
            if name == "tzdata":
                raise ImportError("No module named 'tzdata'")
            return real_import(name, *args, **kwargs)

        def missing(name):
            raise zoneinfo.ZoneInfoNotFoundError(name)

        with mock.patch.object(config_module, "ZoneInfo", missing):
            builtins.__import__ = no_tzdata
            try:
                with self.assertRaises(ConfigError) as ctx:
                    load_config(self.root / "config.yaml")
            finally:
                builtins.__import__ = real_import

        self.assertIn("pip install tzdata", str(ctx.exception))

    def test_sending_window_check(self):
        inside = datetime(2026, 8, 3, 10, 0, tzinfo=IST)
        after_hours = datetime(2026, 8, 3, 22, 0, tzinfo=IST)
        saturday = datetime(2026, 8, 8, 10, 0, tzinfo=IST)
        self.assertTrue(self.cfg.sending.is_sending_time(inside))
        self.assertFalse(self.cfg.sending.is_sending_time(after_hours))
        self.assertFalse(self.cfg.sending.is_sending_time(saturday))


# ---------------------------------------------------------------- scheduling


class TestScheduling(Base):
    def test_delay_skips_weekends(self):
        friday = datetime(2026, 8, 7, 10, 0, tzinfo=IST).astimezone(timezone.utc)
        due = schedule_step(friday, 1, self.cfg, self.rng).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-10")  # Monday

    def test_three_business_days_from_monday(self):
        due = schedule_step(self.now, 3, self.cfg, self.rng).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-06")  # Thursday

    def test_scheduled_time_lands_inside_the_window(self):
        for _ in range(50):
            due = schedule_step(self.now, 2, self.cfg, self.rng)
            self.assertTrue(self.cfg.sending.is_sending_time(due))

    def test_after_hours_rolls_to_next_sending_day(self):
        late = datetime(2026, 8, 7, 23, 0, tzinfo=IST).astimezone(timezone.utc)
        due = schedule_step(late, 0, self.cfg, self.rng).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-10")

    def test_nothing_sends_outside_the_window(self):
        self.add_contact()
        saturday = datetime(2026, 8, 8, 10, 0, tzinfo=IST).astimezone(timezone.utc)
        self.assertEqual(self.run_tick(saturday), [])
        self.assertEqual(self.fake.sent, [])


# ------------------------------------------------------------ quotas and gaps


class TestQuotasAndPool(Base):
    def test_warmup_cap_applies_to_new_mailbox(self):
        # start_cap is 3 even though daily_cap is 10.
        self.assertEqual(remaining_capacity(self.cfg, self.store, self.cfg.mailboxes[0], self.now), 3)

    def test_daily_cap_is_enforced_across_the_pool(self):
        for index in range(20):
            self.add_contact(f"person{index}@example.com")
        # Two mailboxes x start_cap 3 = 6 sends available today.
        moment = self.now
        for _ in range(30):
            self.run_tick(moment)
            moment += timedelta(seconds=61)
        self.assertEqual(len(self.fake.sent), 6)

    def test_gap_between_sends_is_enforced(self):
        for index in range(6):
            self.add_contact(f"p{index}@example.com")
        first = self.run_tick(self.now)
        # One send per mailbox, then both are gated by the 60s gap.
        self.assertEqual(len(first), 2)
        self.assertEqual(self.run_tick(self.now + timedelta(seconds=30)), [])
        self.assertEqual(len(self.run_tick(self.now + timedelta(seconds=61))), 2)

    def test_load_spreads_across_mailboxes(self):
        for index in range(4):
            self.add_contact(f"p{index}@example.com")
        self.run_tick(self.now)
        used = {mailbox_id for mailbox_id, _, _ in self.fake.sent}
        self.assertEqual(used, {"mb1", "mb2"})


# ----------------------------------------------------------- the drip itself


class TestSequenceFlow(Base):
    def _advance_through(self, contact_id, steps=3):
        moment = self.now
        for _ in range(steps):
            self.run_tick(moment)
            contact = self.store.get_contact(contact_id)
            if contact["next_due_at"] is None:
                break
            moment = datetime.fromisoformat(contact["next_due_at"])
        return moment

    def test_full_sequence_completes(self):
        contact_id = self.add_contact()
        self._advance_through(contact_id)
        contact = self.store.get_contact(contact_id)
        self.assertEqual(contact["status"], "completed")
        self.assertEqual(len(self.fake.sent), 3)

    def test_contact_sticks_to_one_mailbox(self):
        contact_id = self.add_contact()
        self._advance_through(contact_id)
        mailboxes = {mailbox_id for mailbox_id, _, _ in self.fake.sent}
        self.assertEqual(len(mailboxes), 1)

    def test_followups_thread_correctly(self):
        contact_id = self.add_contact()
        self._advance_through(contact_id)
        first, second, third = (msg for _, _, msg in self.fake.sent)

        self.assertIsNone(first.get("In-Reply-To"))
        self.assertEqual(second["In-Reply-To"], first["Message-ID"])
        self.assertEqual(third["In-Reply-To"], second["Message-ID"])
        # References must accumulate the whole chain.
        self.assertIn(first["Message-ID"], third["References"])
        self.assertIn(second["Message-ID"], third["References"])
        self.assertTrue(second["Subject"].startswith("Re: "))

    def test_reply_stops_the_sequence(self):
        contact_id = self.add_contact()
        self.run_tick(self.now)
        self.store.set_contact_status(contact_id, "replied", "they answered")

        later = self.now + timedelta(days=7)
        while not self.cfg.sending.is_sending_time(later):
            later += timedelta(hours=1)
        self.run_tick(later)
        self.assertEqual(len(self.fake.sent), 1)

    def test_unsubscribe_header_is_present(self):
        self.add_contact()
        self.run_tick(self.now)
        _, _, msg = self.fake.sent[0]
        self.assertIn("mailto:unsub@test.example", msg["List-Unsubscribe"])

    def test_suppressed_contact_is_never_mailed(self):
        contact_id = self.add_contact("blocked@example.com")
        self.store.suppress("blocked@example.com", "test")
        self.run_tick(self.now)
        self.assertEqual(self.fake.sent, [])
        self.assertEqual(self.store.get_contact(contact_id)["status"], "unsubscribed")

    def test_missing_merge_field_pauses_instead_of_sending_broken_mail(self):
        path = self.root / "sequences" / "test.yaml"
        path.write_text(
            'name: test\nsteps:\n  - id: 1\n    delay_business_days: 0\n'
            '    subject: "Hi {{first_name}}"\n    body: |\n      Re {{trigger}}\n',
            encoding="utf-8",
        )
        self.sequences = load_all(self.cfg.sequences_dir)
        contact_id = self.add_contact()
        results = self.run_tick(self.now)
        self.assertEqual(self.fake.sent, [])
        self.assertEqual(self.store.get_contact(contact_id)["status"], "paused")
        self.assertIn("trigger", results[0].detail)

    def test_dry_run_sends_nothing(self):
        contact_id = self.add_contact()
        results = self.run_tick(self.now, dry_run=True)
        self.assertEqual(self.fake.sent, [])
        self.assertEqual(results[0].outcome, "dry-run")
        self.assertEqual(self.store.get_contact(contact_id)["next_step"], 1)


# ----------------------------------------------------------- failure handling


class TestFailures(Base):
    def test_permanent_failure_bounces_and_suppresses(self):
        contact_id = self.add_contact()
        self.fake.fail_with = sender.PermanentSendError("550 no such user")
        self.run_tick(self.now)
        self.assertEqual(self.store.get_contact(contact_id)["status"], "bounced")
        self.assertTrue(self.store.is_suppressed("dana@example.com"))

    def test_transient_failure_retries_then_gives_up(self):
        contact_id = self.add_contact()
        self.fake.fail_with = sender.SendError("connection reset")

        moment = self.now
        for _ in range(scheduler.MAX_ATTEMPTS):
            self.run_tick(moment)
            moment += scheduler.RETRY_DELAY + timedelta(seconds=1)

        contact = self.store.get_contact(contact_id)
        self.assertEqual(contact["status"], "paused")
        self.assertEqual(self.store.attempts_for(contact_id, 1), scheduler.MAX_ATTEMPTS)


# ---------------------------------------------------------------------- store


class TestStore(Base):
    def test_duplicate_email_is_not_reimported(self):
        first_id, created_first = self.store.upsert_contact({"email": "x@y.com"}, "test")
        second_id, created_second = self.store.upsert_contact({"email": "X@Y.COM"}, "test")
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first_id, second_id)

    def test_custom_columns_become_merge_fields(self):
        contact_id = self.add_contact(trigger="raised a Series A")
        rendered = render_step(
            {"id": 1, "subject": "x", "body": "Saw you {{trigger}}"},
            self.store.get_contact(contact_id), self.cfg.identity,
        )
        self.assertIn("Saw you raised a Series A", rendered.body)

    def test_stats_counts_sends(self):
        self.add_contact()
        self.run_tick(self.now)
        self.assertEqual(self.store.stats()["sent"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
