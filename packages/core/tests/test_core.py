"""Regression net for the ported deliverability logic.

Run with:  python -m unittest discover -s packages/core/tests -v

These are the tests that came across from the single-user CLI, re-pointed at
`outreach_core`, plus the ones the rewrite needs and the CLI never had: the
touch ceiling, the minimum gap, and the cross-user guard. Stdlib only, so this
suite runs on a clean checkout with nothing installed.
"""

from __future__ import annotations

import random
import sys
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from outreach_core.classify import (  # noqa: E402
    AUTOREPLY_DEFER, SOFT_BOUNCE_DEFER, Classification, Inbound, Verdict, classify,
    dsn_status, is_autoreply, is_bounce, is_permanent_bounce, is_transient_bounce,
)
from outreach_core.limits import (  # noqa: E402
    MAX_CYCLES, MAX_TOUCHES, MIN_BUSINESS_DAYS_BETWEEN_TOUCHES, RESET_AFTER,
    RecipientGuard, WarmupPolicy, may_schedule_touch, recipient_key,
    remaining_touches, starts_new_cycle,
)
from outreach_core.mime import (  # noqa: E402
    Outgoing, SenderIdentity, build_message, extend_references, signature, to_gmail_raw,
)
from outreach_core.scheduling import (  # noqa: E402
    SEND_SOON_DELAY, ScheduleError, SendingWindow, next_sending_day, schedule_step,
)
from outreach_core.templating import (  # noqa: E402
    TemplateError, expand_spintax, lint, render, render_draft, template_fields,
)

IST = ZoneInfo("Asia/Kolkata")

# Monday 2026-08-03, 10:00 IST - inside the sending window.
MONDAY = datetime(2026, 8, 3, 10, 0, tzinfo=IST).astimezone(timezone.utc)


def window(**overrides) -> SendingWindow:
    base = dict(
        timezone="Asia/Kolkata",
        start=time(9, 0),
        end=time(17, 0),
        days=("mon", "tue", "wed", "thu", "fri"),
        min_gap_seconds=60,
        max_gap_seconds=60,
    )
    base.update(overrides)
    return SendingWindow(**base)


# --------------------------------------------------------------- templating


class TestTemplating(unittest.TestCase):
    def test_merge_fields_and_fallback(self):
        out = render("Hi {{first_name}} at {{company|your team}}", {"first_name": "Dana"})
        self.assertEqual(out, "Hi Dana at your team")

    def test_missing_field_is_reported(self):
        missing: list[str] = []
        render("Hi {{first_name}}, re {{hook}}", {"first_name": "Dana"}, missing=missing)
        self.assertEqual(missing, ["hook"])

    def test_spintax_picks_one_option(self):
        for _ in range(20):
            self.assertIn(expand_spintax("{saw|noticed|spotted}"), {"saw", "noticed", "spotted"})

    def test_merge_values_are_not_respun(self):
        # A value containing pipes inside braces must survive verbatim.
        self.assertEqual(render("{{note}}", {"note": "{a|b}"}), "{a|b}")

    def test_template_fields_reports_optionality(self):
        fields = template_fields("{{a}} {{b|x}} {{a|y}}")
        self.assertFalse(fields["a"])  # one use has no fallback, so it is required
        self.assertTrue(fields["b"])

    def test_followup_subject_becomes_re(self):
        rendered = render_draft(
            None, "Following up.", {}, thread_subject="Hi Dana - about ExampleCorp"
        )
        self.assertEqual(rendered.subject, "Re: Hi Dana - about ExampleCorp")

    def test_re_prefix_is_not_doubled(self):
        rendered = render_draft(None, "x", {}, thread_subject="Re: Already threaded")
        self.assertEqual(rendered.subject, "Re: Already threaded")

    def test_draft_without_subject_or_thread_is_an_error(self):
        with self.assertRaises(TemplateError):
            render_draft(None, "body", {})

    def test_personal_mail_gets_no_footer(self):
        rendered = render_draft("Hi", "Body text", {})
        self.assertEqual(rendered.body, "Body text")
        self.assertNotIn("unsubscribe", rendered.body.lower())

    def test_tech_acronyms_do_not_trip_the_caps_check(self):
        self.assertEqual(lint("I fine-tuned BERT with CUDA and PyTorch."), [])
        self.assertIn("ALL-CAPS", " ".join(lint("THIS IS URGENT")))

    def test_lint_flags_spam_triggers_and_links(self):
        joined = " ".join(lint("ACT NOW click here https://a.com https://b.com FREE!!"))
        self.assertIn("spam trigger", joined)
        self.assertIn("links", joined)

    def test_lint_flags_length_and_markup(self):
        self.assertIn("chars", " ".join(lint("x" * 1300)))
        self.assertIn("HTML markup", " ".join(lint("<table><tr></tr></table>")))


# ---------------------------------------------------------------- scheduling


class TestScheduling(unittest.TestCase):
    def setUp(self):
        self.window = window()
        self.rng = random.Random(1234)

    def test_delay_skips_weekends(self):
        friday = datetime(2026, 8, 7, 10, 0, tzinfo=IST).astimezone(timezone.utc)
        due = schedule_step(friday, 1, self.window, self.rng).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-10")  # Monday

    def test_three_business_days_from_monday(self):
        due = schedule_step(MONDAY, 3, self.window, self.rng).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-06")  # Thursday

    def test_scheduled_time_lands_inside_the_window(self):
        for _ in range(50):
            due = schedule_step(MONDAY, 2, self.window, self.rng)
            self.assertTrue(self.window.is_sending_time(due))

    def test_after_hours_rolls_to_next_sending_day(self):
        late = datetime(2026, 8, 7, 23, 0, tzinfo=IST).astimezone(timezone.utc)
        due = schedule_step(late, 0, self.window, self.rng).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-10")

    # -------------------------------------------------- "as soon as possible"
    #
    # Never the current instant. A due time that is already past the moment it
    # is written cannot be displayed honestly - see SEND_SOON_DELAY.

    def test_asap_is_placed_ahead_of_now_not_at_it(self):
        """Whatever else it is, it is in the future. Every time, not usually."""
        afternoon = datetime(2026, 8, 3, 16, 30, tzinfo=IST).astimezone(timezone.utc)
        for _ in range(200):
            due = schedule_step(afternoon, 0, self.window, random.Random())
            self.assertGreater(due, afternoon)

    def test_asap_lands_two_minutes_out(self):
        # Seed 1 picks a slot earlier than 16:30, so the "already passed, send
        # as soon as possible" branch is the one taken - which is the branch
        # under test, and asserting it unconditionally is the point.
        afternoon = datetime(2026, 8, 3, 16, 30, tzinfo=IST).astimezone(timezone.utc)
        due = schedule_step(afternoon, 0, self.window, random.Random(1))
        self.assertEqual(due, afternoon + SEND_SOON_DELAY)

    def test_asap_never_lands_outside_the_window(self):
        """The edge the delay introduces: two minutes past 16:59 is closing time.

        Scheduling one minute after the window shuts produces a row the worker
        refuses for the rest of the evening, so this has to roll to tomorrow
        instead.
        """
        closing = datetime(2026, 8, 3, 16, 59, tzinfo=IST).astimezone(timezone.utc)
        for _ in range(50):
            due = schedule_step(closing, 0, self.window, random.Random())
            self.assertTrue(self.window.is_sending_time(due))

    def test_asap_at_the_very_edge_rolls_to_the_next_day(self):
        closing = datetime(2026, 8, 3, 16, 59, tzinfo=IST).astimezone(timezone.utc)
        due = schedule_step(closing, 0, self.window, random.Random(7)).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-04")

    def test_is_sending_time(self):
        self.assertTrue(self.window.is_sending_time(datetime(2026, 8, 3, 10, 0, tzinfo=IST)))
        self.assertFalse(self.window.is_sending_time(datetime(2026, 8, 3, 22, 0, tzinfo=IST)))
        self.assertFalse(self.window.is_sending_time(datetime(2026, 8, 8, 10, 0, tzinfo=IST)))

    def test_window_respects_each_users_own_days(self):
        # A user who sends on weekends gets Saturday; the default user does not.
        weekend = window(days=("sat", "sun"))
        saturday = date(2026, 8, 8)
        self.assertEqual(next_sending_day(saturday, weekend), saturday)
        self.assertEqual(next_sending_day(saturday, self.window), date(2026, 8, 10))

    def test_backwards_window_is_rejected(self):
        with self.assertRaises(ScheduleError):
            window(start=time(18, 0), end=time(9, 0))

    def test_unknown_day_is_rejected(self):
        with self.assertRaises(ScheduleError):
            window(days=("mon", "funday"))

    def test_unknown_timezone_reports_a_typo(self):
        with self.assertRaises(ScheduleError) as ctx:
            window(timezone="Asia/Delhi").tz
        self.assertIn("Unknown timezone", str(ctx.exception))

    def test_missing_tzdata_says_how_to_fix_it(self):
        """Windows ships no IANA database - the error must not look like a typo."""
        import builtins
        import zoneinfo
        from unittest import mock

        from outreach_core import scheduling

        real_import = builtins.__import__

        def no_tzdata(name, *args, **kwargs):
            if name == "tzdata":
                raise ImportError("No module named 'tzdata'")
            return real_import(name, *args, **kwargs)

        def missing(name):
            raise zoneinfo.ZoneInfoNotFoundError(name)

        with mock.patch.object(scheduling, "ZoneInfo", missing):
            builtins.__import__ = no_tzdata
            try:
                with self.assertRaises(ScheduleError) as ctx:
                    scheduling.resolve_timezone("Asia/Kolkata")
            finally:
                builtins.__import__ = real_import

        self.assertIn("pip install tzdata", str(ctx.exception))


# ------------------------------------------------------------- warmup and caps


class TestWarmup(unittest.TestCase):
    def setUp(self):
        self.policy = WarmupPolicy(start_cap=3, increment_per_day=2, max_cap=10)

    def test_new_account_starts_at_the_bottom_of_the_ramp(self):
        cap = self.policy.cap_for(daily_cap=40, first_send_date=None, today=date(2026, 8, 3))
        self.assertEqual(cap, 3)

    def test_ramp_increases_with_days_active(self):
        started = date(2026, 8, 3)
        caps = [
            self.policy.cap_for(daily_cap=40, first_send_date=started, today=started + timedelta(days=n))
            for n in range(5)
        ]
        self.assertEqual(caps, [3, 5, 7, 9, 10])  # clamped by max_cap

    def test_max_cap_is_the_ceiling(self):
        cap = self.policy.cap_for(
            daily_cap=40, first_send_date=date(2020, 1, 1), today=date(2026, 8, 3)
        )
        self.assertEqual(cap, 10)

    def test_per_user_hard_cap_wins_over_the_ramp(self):
        cap = self.policy.cap_for(
            daily_cap=2, first_send_date=date(2020, 1, 1), today=date(2026, 8, 3)
        )
        self.assertEqual(cap, 2)

    def test_disabled_warmup_uses_the_flat_cap(self):
        policy = WarmupPolicy(enabled=False)
        cap = policy.cap_for(daily_cap=7, first_send_date=None, today=date(2026, 8, 3))
        self.assertEqual(cap, 7)


# ------------------------------------------------------------- per-target caps


class TestTouchLimits(unittest.TestCase):
    def test_a_fourth_touch_is_never_allowed(self):
        self.assertTrue(may_schedule_touch(status="active", touches_sent=2))
        decision = may_schedule_touch(status="active", touches_sent=MAX_TOUCHES)
        self.assertFalse(decision)
        self.assertIn("touches already sent", decision.reason)

    def test_remaining_touches_never_goes_negative(self):
        self.assertEqual(remaining_touches(0), MAX_TOUCHES)
        self.assertEqual(remaining_touches(99), 0)

    def test_reply_bounce_and_optout_end_the_sequence_permanently(self):
        for status in ("replied", "bounced", "opted_out", "suppressed"):
            decision = may_schedule_touch(status=status, touches_sent=0)
            self.assertFalse(decision, f"{status} should stop the sequence")
            self.assertIn(status, decision.reason)

    def test_undeliverable_address_blocks_sending(self):
        self.assertFalse(
            may_schedule_touch(status="active", touches_sent=0, verification="undeliverable")
        )

    def test_risky_address_is_allowed_through(self):
        self.assertTrue(
            may_schedule_touch(status="active", touches_sent=0, verification="risky")
        )

    def test_minimum_gap_between_touches_spans_business_days(self):
        # Three business days from Monday is Thursday, not Wednesday-plus-a-weekend.
        rng = random.Random(7)
        due = schedule_step(
            MONDAY, MIN_BUSINESS_DAYS_BETWEEN_TOUCHES, window(), rng
        ).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-06")

        # And from Thursday it lands the following Tuesday, skipping the weekend.
        thursday = datetime(2026, 8, 6, 10, 0, tzinfo=IST).astimezone(timezone.utc)
        due = schedule_step(
            thursday, MIN_BUSINESS_DAYS_BETWEEN_TOUCHES, window(), rng
        ).astimezone(IST)
        self.assertEqual(due.date().isoformat(), "2026-08-11")


# ---------------------------------------------------------- cross-user guard


class TestRecipientGuard(unittest.TestCase):
    def setUp(self):
        self.guard = RecipientGuard(window=timedelta(days=7), max_contacts=3)
        self.now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)

    def test_key_is_stable_and_case_insensitive(self):
        secret = b"server-secret"
        self.assertEqual(
            recipient_key("Dana@Example.com ", secret),
            recipient_key("dana@example.com", secret),
        )

    def test_key_depends_on_the_secret(self):
        # This is the whole point: without the secret the table is not a
        # lookup table of who is being emailed.
        self.assertNotEqual(
            recipient_key("dana@example.com", b"secret-one"),
            recipient_key("dana@example.com", b"secret-two"),
        )

    def test_empty_secret_is_refused(self):
        with self.assertRaises(ValueError):
            recipient_key("dana@example.com", b"")

    def test_pile_on_is_blocked_at_the_threshold(self):
        recent = self.now - timedelta(days=1)
        self.assertFalse(self.guard.blocks(contact_count=2, last_contacted_at=recent, now=self.now))
        self.assertTrue(self.guard.blocks(contact_count=3, last_contacted_at=recent, now=self.now))

    def test_count_older_than_the_window_does_not_block(self):
        stale = self.now - timedelta(days=30)
        self.assertFalse(self.guard.blocks(contact_count=99, last_contacted_at=stale, now=self.now))

    def test_never_contacted_does_not_block(self):
        self.assertFalse(self.guard.blocks(contact_count=0, last_contacted_at=None, now=self.now))

    def test_count_resets_once_the_window_lapses(self):
        stale = self.now - timedelta(days=30)
        self.assertEqual(
            self.guard.next_count(contact_count=9, last_contacted_at=stale, now=self.now), 1
        )
        recent = self.now - timedelta(hours=1)
        self.assertEqual(
            self.guard.next_count(contact_count=9, last_contacted_at=recent, now=self.now), 10
        )


# --------------------------------------------------------------------- MIME


class FakeGmail:
    """Stands in for users.messages.send.

    Mirrors the behaviour that matters for threading: Gmail assigns its own
    Message-ID and returns an id and threadId, so the caller cannot rely on a
    Message-ID it set itself.
    """

    def __init__(self):
        self.sent: list[tuple[str, object]] = []

    def send(self, sender: SenderIdentity, out: Outgoing, thread_id: str | None = None):
        msg = build_message(sender, out)
        assigned = f"<gmail-{len(self.sent) + 1}@mail.gmail.com>"
        msg["Message-ID"] = assigned
        self.sent.append((out.to_email, msg))
        return {
            "id": f"m{len(self.sent)}",
            "threadId": thread_id or "t1",
            "messageId": assigned,
        }


class TestMime(unittest.TestCase):
    def setUp(self):
        self.sender = SenderIdentity(email="me@send.test", from_name="Test Sender")

    def test_message_id_is_left_to_gmail(self):
        msg = build_message(self.sender, Outgoing("d@e.com", "Hi", "Body"))
        self.assertIsNone(msg.get("Message-ID"))

    def test_personal_mail_omits_list_unsubscribe_header(self):
        msg = build_message(self.sender, Outgoing("d@e.com", "Hi", "Body"))
        self.assertIsNone(msg.get("List-Unsubscribe"))
        self.assertIsNone(msg.get("List-Unsubscribe-Post"))

    def test_body_is_plain_text(self):
        msg = build_message(self.sender, Outgoing("d@e.com", "Hi", "Body"))
        self.assertEqual(msg.get_content_type(), "text/plain")
        self.assertEqual(msg.get_payload(decode=True).decode("utf-8").strip(), "Body")

    def test_from_header_carries_the_display_name(self):
        msg = build_message(self.sender, Outgoing("d@e.com", "Hi", "Body"))
        self.assertEqual(msg["From"], "Test Sender <me@send.test>")

    def test_reply_to_is_set_when_present(self):
        sender = SenderIdentity("me@send.test", "Test Sender", reply_to="other@send.test")
        msg = build_message(sender, Outgoing("d@e.com", "Hi", "Body"))
        self.assertEqual(msg["Reply-To"], "other@send.test")

    def test_followups_thread_correctly_across_three_touches(self):
        gmail = FakeGmail()
        references = ""
        last_msgid = None
        subject = "Hi Dana - about ExampleCorp"

        for touch in range(MAX_TOUCHES):
            rendered = render_draft(
                subject if touch == 0 else None,
                f"Touch {touch + 1}",
                {},
                thread_subject=subject,
            )
            result = gmail.send(
                self.sender,
                Outgoing(
                    to_email="d@e.com",
                    subject=rendered.subject,
                    body=rendered.body,
                    in_reply_to=last_msgid,
                    references=references,
                ),
            )
            last_msgid = result["messageId"]
            references = extend_references(references, last_msgid)

        first, second, third = (msg for _, msg in gmail.sent)
        self.assertIsNone(first.get("In-Reply-To"))
        self.assertEqual(second["In-Reply-To"], first["Message-ID"])
        self.assertEqual(third["In-Reply-To"], second["Message-ID"])
        # References must accumulate the whole chain, not just the parent.
        self.assertIn(first["Message-ID"], third["References"])
        self.assertIn(second["Message-ID"], third["References"])
        self.assertTrue(second["Subject"].startswith("Re: "))
        self.assertEqual(len(gmail.sent), MAX_TOUCHES)

    def test_gmail_raw_is_urlsafe_base64(self):
        msg = build_message(self.sender, Outgoing("d@e.com", "Hi", "Body"))
        raw = to_gmail_raw(msg)
        self.assertNotIn("+", raw)
        self.assertNotIn("/", raw)
        import base64

        self.assertIn(b"Subject: Hi", base64.urlsafe_b64decode(raw))

    def test_every_body_shape_survives_the_no_wrap_policy(self):
        """The send policy disables wrapping; it must not disable encoding.

        A `max_line_length` under 4 reaches `quoprimime.body_encode` through
        `set_content` and raises, which took down every send until the limit
        became 998 instead of 0. One case per encoding branch - plain ASCII,
        non-ASCII, and a line past the RFC 5322 limit - each checked by
        reading the body back out of the serialized message.
        """
        import email as email_mod
        from email.policy import default as default_policy

        bodies = {
            "ascii": "Hi Dana,\n\nQuick note about ExampleCorp.\n\nAtharv",
            "non_ascii": "Hi Dana — I read your post. It’s good.\n\nAtharv",
            "long_line": "word " * 400,
        }
        for label, body in bodies.items():
            with self.subTest(body=label):
                msg = build_message(self.sender, Outgoing("d@e.com", "Hi", body))
                raw = msg.as_bytes()
                parsed = email_mod.message_from_bytes(raw, policy=default_policy)
                self.assertEqual(parsed.get_content().rstrip("\n"), body.rstrip("\n"))
                # 998 is a hard limit, not a preference - Gmail may accept a
                # longer line, but the next hop is not required to.
                self.assertLessEqual(max(len(line) for line in raw.split(b"\n")), 998)

    def test_headers_are_not_folded(self):
        """Long subjects and References chains go out on one line."""
        subject = "Hi Dana - about the ExampleCorp platform role you posted last week"
        references = " ".join(f"<gmail-{n}@mail.gmail.com>" for n in range(8))
        msg = build_message(
            self.sender,
            Outgoing("d@e.com", subject, "Body", in_reply_to="<x@mail.gmail.com>", references=references),
        )
        raw = msg.as_bytes()
        self.assertIn(f"Subject: {subject}".encode(), raw)
        self.assertIn(f"{references} <x@mail.gmail.com>".encode(), raw)


class TestSignature(unittest.TestCase):
    def test_nothing_configured_appends_nothing(self):
        """An empty profile must not put a bare separator on every email."""
        self.assertEqual(signature("", {}), "")
        self.assertEqual(signature("   ", {"portfolio": "  "}), "")

    def test_portfolio_and_name_only(self):
        self.assertEqual(
            signature("Dana", {"portfolio": "https://dana.dev"}),
            "\n\nDana\nPortfolio: https://dana.dev",
        )

    def test_exactly_one_link_even_when_several_qualify(self):
        """The body already spends the one URL a cold email can afford."""
        block = signature(
            "Dana",
            {
                "portfolio": "https://p",
                "linkedin": "https://l",
                "github": "https://g",
                "resume": "https://r",
            },
        )
        self.assertEqual(block.count("http"), 1)
        self.assertIn("Portfolio: https://p", block)

    def test_falls_back_through_the_chain_in_order(self):
        links = {"linkedin": "https://l", "github": "https://g", "resume": "https://r"}
        self.assertIn("LinkedIn: https://l", signature("", links))
        self.assertIn("GitHub: https://g", signature("", {k: v for k, v in links.items() if k != "linkedin"}))
        self.assertIn("Resume: https://r", signature("", {"resume": "https://r"}))

    def test_other_is_never_used(self):
        """An unlabelled link is not worth the single slot."""
        self.assertEqual(signature("Dana", {"other": "https://x"}), "\n\nDana")

    def test_name_only_when_every_link_is_empty(self):
        self.assertEqual(
            signature("Dana", {"portfolio": "", "linkedin": "", "github": "", "resume": ""}),
            "\n\nDana",
        )

    def test_key_matching_ignores_case(self):
        """Profile keys are typed by hand, so "Portfolio" must work too."""
        self.assertIn("Portfolio: https://p", signature("", {"Portfolio": "https://p"}))

    def test_no_rfc3676_delimiter(self):
        """Gmail hides what follows "--", which is exactly what this shows."""
        self.assertNotIn("--", signature("Dana", {"portfolio": "https://dana.dev"}))

    # ------------------------------------------- a body that signed itself
    #
    # The prompt forbids a sign-off, and a model may write one anyway. On a
    # first touch that put the sender's name in twice, three lines apart.

    def test_name_is_skipped_when_the_body_already_signed_off(self):
        body = "...does that fit?\n\nBest,\nDana"
        self.assertEqual(
            signature("Dana", {"portfolio": "https://dana.dev"}, body),
            "\n\nPortfolio: https://dana.dev",
        )

    def test_nothing_is_appended_when_signed_off_and_no_link(self):
        self.assertEqual(signature("Dana", {}, "...does that fit?\n\nBest,\nDana"), "")

    def test_the_body_is_never_edited(self):
        """The whole point of skipping rather than stripping."""
        body = "...does that fit?\n\nBest,\nDana"
        signature("Dana", {"portfolio": "https://dana.dev"}, body)
        self.assertEqual(body, "...does that fit?\n\nBest,\nDana")

    def test_a_name_inside_a_sentence_is_not_a_sign_off(self):
        """Only a whole last line counts, or an ordinary mention loses the name."""
        body = "I am Dana"
        self.assertEqual(signature("Dana", {}, body), "\n\nDana")

    def test_trailing_blank_lines_do_not_hide_the_sign_off(self):
        body = "...does that fit?\n\nBest,\nDana\n\n  \n"
        self.assertEqual(signature("Dana", {}, body), "")

    def test_case_and_a_trailing_comma_still_match(self):
        self.assertEqual(signature("Dana", {}, "...fit?\n\ndana,"), "")

    def test_an_unsigned_body_is_unaffected(self):
        body = "...does that fit?"
        self.assertEqual(
            signature("Dana", {"portfolio": "https://dana.dev"}, body),
            "\n\nDana\nPortfolio: https://dana.dev",
        )

    def test_someone_elses_name_on_the_last_line_is_not_a_sign_off(self):
        self.assertEqual(signature("Dana", {}, "...fit?\n\nSam"), "\n\nDana")


# ----------------------------------------------------------- classification


def inbound(subject="", from_addr="dana@example.com", body="", **headers) -> Inbound:
    return Inbound(headers={"Subject": subject, "From": from_addr, **headers}, body=body)


class TestClassify(unittest.TestCase):
    def test_genuine_reply_stops_the_sequence(self):
        result = classify(inbound(subject="Re: your note", body="Sure, let's talk Tuesday."))
        self.assertEqual(result.verdict, Verdict.REPLY)
        self.assertTrue(result.stops_sequence)
        self.assertFalse(result.suppresses)

    def test_bounce_is_detected_by_sender(self):
        self.assertTrue(is_bounce(inbound(from_addr="mailer-daemon@googlemail.com")))
        result = classify(inbound(from_addr="postmaster@example.com", subject="Undeliverable"))
        self.assertEqual(result.verdict, Verdict.BOUNCE)
        self.assertTrue(result.suppresses)

    def test_bounce_is_detected_by_subject(self):
        self.assertEqual(
            classify(inbound(subject="Address not found")).verdict, Verdict.BOUNCE
        )

    def test_autoreply_defers_instead_of_stopping(self):
        """The single most important behaviour, and the easiest to regress."""
        result = classify(inbound(subject="Out of office: back Monday"))
        self.assertEqual(result.verdict, Verdict.AUTOREPLY)
        self.assertFalse(result.stops_sequence)
        self.assertFalse(result.suppresses)
        self.assertEqual(result.defer, AUTOREPLY_DEFER)

    def test_autoreply_is_detected_by_header(self):
        self.assertTrue(is_autoreply(inbound(**{"Auto-Submitted": "auto-replied"})))
        self.assertTrue(is_autoreply(inbound(**{"X-Autoreply": "yes"})))
        self.assertTrue(is_autoreply(inbound(**{"Precedence": "auto_reply"})))

    def test_opt_out_suppresses_permanently(self):
        result = classify(inbound(body="Please remove me from your list."))
        self.assertEqual(result.verdict, Verdict.OPT_OUT)
        self.assertTrue(result.stops_sequence)
        self.assertTrue(result.suppresses)

    def test_optout_in_subject_counts(self):
        self.assertEqual(classify(inbound(subject="unsubscribe")).verdict, Verdict.OPT_OUT)

    def test_vacation_footer_does_not_count_as_an_opt_out(self):
        # An out-of-office carrying a corporate "unsubscribe" footer must not
        # permanently suppress someone who is merely on leave.
        result = classify(
            inbound(
                subject="Automatic reply: on annual leave",
                body="I am away until the 20th.\n\nTo unsubscribe, click here.",
            )
        )
        self.assertEqual(result.verdict, Verdict.AUTOREPLY)
        self.assertFalse(result.suppresses)

    def test_quoted_history_beyond_the_scan_window_is_ignored(self):
        body = "Happy to chat.\n\n" + ("quoted history line\n" * 400) + "unsubscribe"
        self.assertEqual(classify(inbound(body=body)).verdict, Verdict.REPLY)

    def test_headers_are_matched_case_insensitively(self):
        message = Inbound(headers={"auto-submitted": "auto-generated"})
        self.assertTrue(is_autoreply(message))

    def test_from_gmail_payload_headers(self):
        message = Inbound.from_gmail(
            [
                {"name": "Subject", "value": "Out of office"},
                {"name": "From", "value": "Dana Smith <Dana@Example.com>"},
            ],
            body="away",
        )
        self.assertEqual(message.from_address, "dana@example.com")
        self.assertEqual(classify(message).verdict, Verdict.AUTOREPLY)

    def test_bounce_body_names_the_failed_address(self):
        message = inbound(
            from_addr="mailer-daemon@googlemail.com",
            subject="Delivery Status Notification (Failure)",
            body="Your message to nobody@example.com was not delivered.",
        )
        from outreach_core.classify import bounced_addresses

        self.assertIn("nobody@example.com", bounced_addresses(message))

    def test_classification_is_a_value(self):
        self.assertIsInstance(classify(inbound(body="yes")), Classification)


# ------------------------------------------------------------- touch cycles


class TestTouchCycles(unittest.TestCase):
    """A completed sequence may run again after a cooldown, twice in total.

    The two properties worth pinning: the ceiling is a real ceiling however
    long an account lives, and a cycle can never revive somebody who replied.
    """

    def setUp(self):
        self.now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        self.long_ago = self.now - RESET_AFTER - timedelta(days=1)
        self.recently = self.now - timedelta(days=2)

    def decide(self, **kwargs):
        base = dict(status="completed", touches_sent=MAX_TOUCHES, now=self.now)
        return may_schedule_touch(**{**base, **kwargs})

    def test_a_finished_sequence_is_blocked_during_the_cooldown(self):
        decision = self.decide(cycles_used=1, last_cycle_ended_at=self.recently)
        self.assertFalse(decision.allowed)
        self.assertIn("may resume", decision.reason)

    def test_it_resumes_once_the_cooldown_has_passed(self):
        self.assertTrue(self.decide(cycles_used=1, last_cycle_ended_at=self.long_ago))

    def test_the_ceiling_holds_however_long_you_wait(self):
        decision = self.decide(
            cycles_used=MAX_CYCLES, last_cycle_ended_at=self.now - timedelta(days=3650)
        )
        self.assertFalse(decision.allowed)
        self.assertIn("end of it", decision.reason)

    def test_a_replied_target_never_cycles(self):
        """The safety property. `TERMINAL_STATUSES` is checked before the cycle
        branch, so no amount of elapsed time revives someone who answered."""
        for status in ("replied", "bounced", "opted_out", "suppressed"):
            decision = self.decide(
                status=status, cycles_used=0, last_cycle_ended_at=self.long_ago
            )
            self.assertFalse(decision.allowed, status)
            self.assertIn("permanently", decision.reason)

    def test_an_undeliverable_address_never_cycles(self):
        self.assertFalse(
            self.decide(
                verification="undeliverable",
                cycles_used=0,
                last_cycle_ended_at=self.long_ago,
            )
        )

    def test_without_a_recorded_ending_there_is_no_cooldown_to_measure(self):
        """Targets that completed before cycles existed have a NULL stamp.
        Refuse rather than treat the missing value as "long ago"."""
        self.assertFalse(self.decide(cycles_used=0, last_cycle_ended_at=None))

    def test_a_sequence_in_progress_is_unaffected(self):
        self.assertTrue(may_schedule_touch(status="active", touches_sent=1))

    def test_starts_new_cycle_agrees_with_the_decision(self):
        """The two are asked separately - a reset is a write, not just a
        permission - so they must not be able to disagree."""
        cases = [
            (MAX_TOUCHES, 1, self.long_ago, True),
            (MAX_TOUCHES, 1, self.recently, False),
            (MAX_TOUCHES, MAX_CYCLES, self.long_ago, False),
            (1, 0, None, False),
        ]
        for touches, cycles, ended, expected in cases:
            self.assertEqual(
                starts_new_cycle(
                    touches_sent=touches,
                    cycles_used=cycles,
                    last_cycle_ended_at=ended,
                    now=self.now,
                ),
                expected,
                f"touches={touches} cycles={cycles}",
            )

    def test_two_sequences_is_six_emails_not_nine(self):
        """Walks the whole lifecycle the way the send path drives it, because
        the off-by-one this guards against only shows up over two full runs."""
        touches, cycles, ended = 0, 0, None
        sent = 0

        for _ in range(20):  # far more iterations than should be permitted
            if not may_schedule_touch(
                status="completed" if touches >= MAX_TOUCHES else "active",
                touches_sent=touches,
                cycles_used=cycles,
                last_cycle_ended_at=ended,
                now=self.now,
            ):
                break
            if starts_new_cycle(
                touches_sent=touches,
                cycles_used=cycles,
                last_cycle_ended_at=ended,
                now=self.now,
            ):
                touches = 0
            touches += 1
            sent += 1
            if touches >= MAX_TOUCHES:
                # `_close_or_advance` counts the run as it finishes.
                cycles += 1
                ended = self.long_ago  # cooldown already served, worst case

        self.assertEqual(cycles, MAX_CYCLES)
        self.assertEqual(sent, MAX_TOUCHES * MAX_CYCLES)


# ------------------------------------------------------- hard vs soft bounces


def dsn(status: str, subject="Delivery Status Notification (Failure)") -> Inbound:
    """A bounce carrying a machine-readable delivery status."""
    return Inbound(
        headers={"Subject": subject, "From": "mailer-daemon@googlemail.com"},
        body="Your message was not delivered.",
        delivery_status=(
            "Reporting-MTA: dns; googlemail.com\n"
            "Final-Recipient: rfc822; nobody@example.com\n"
            f"Status: {status}\n"
            "Diagnostic-Code: smtp; 550 5.1.1 No such user\n"
        ),
    )


class TestBouncePermanence(unittest.TestCase):
    """A dead mailbox and a full one arrive looking identical to the subject
    heuristics. Only the RFC 3463 status tells them apart, and only a permanent
    one may be recorded against the address for every user of the platform."""

    def test_a_hard_bounce_is_permanent_and_stops_the_sequence(self):
        result = classify(dsn("5.1.1"))
        self.assertEqual(result.verdict, Verdict.BOUNCE)
        self.assertTrue(result.permanent)
        self.assertTrue(result.stops_sequence)
        self.assertTrue(result.suppresses)
        self.assertIsNone(result.defer)

    def test_a_soft_bounce_defers_instead_of_stopping(self):
        result = classify(dsn("4.2.2"))
        self.assertEqual(result.verdict, Verdict.BOUNCE)
        self.assertFalse(result.permanent)
        self.assertFalse(result.stops_sequence)
        # A full mailbox must not land on the user's do-not-contact list.
        self.assertFalse(result.suppresses)
        self.assertEqual(result.defer, SOFT_BOUNCE_DEFER)

    def test_a_bounce_without_a_parseable_status_is_never_global(self):
        """The subject and sender heuristics still catch it, so the sequence
        stops - but a guess must not kill the address for everybody."""
        result = classify(
            inbound(
                from_addr="mailer-daemon@googlemail.com",
                subject="Undeliverable: your message",
                body="delivery failed",
            )
        )
        self.assertEqual(result.verdict, Verdict.BOUNCE)
        self.assertFalse(result.permanent)
        self.assertTrue(result.stops_sequence)
        self.assertTrue(result.suppresses)

    def test_status_is_read_only_from_the_delivery_status_part(self):
        """A bounce quotes the original message. A line reading 'Status: 5.0.0'
        in that quoted copy must not be mistaken for the report's own."""
        message = Inbound(
            headers={"Subject": "Undeliverable", "From": "mailer-daemon@example.com"},
            body="Original message follows:\nStatus: 5.0.0\n",
            delivery_status="",
        )
        self.assertIsNone(dsn_status(message))
        self.assertFalse(classify(message).permanent)

    def test_status_parsing(self):
        self.assertEqual(dsn_status(dsn("5.7.1")), "5.7.1")
        self.assertEqual(dsn_status(dsn("4.4.7")), "4.4.7")
        self.assertTrue(is_permanent_bounce("5.1.1"))
        self.assertFalse(is_permanent_bounce("4.1.1"))
        self.assertFalse(is_permanent_bounce(None))
        self.assertTrue(is_transient_bounce("4.2.2"))
        self.assertFalse(is_transient_bounce("5.2.2"))

    def test_status_is_matched_case_insensitively_and_with_leading_space(self):
        message = Inbound(
            headers={"Subject": "Undeliverable", "From": "postmaster@example.com"},
            delivery_status="  status: 5.1.1\n",
        )
        self.assertEqual(dsn_status(message), "5.1.1")

    def test_an_autoreply_still_defers_and_does_not_suppress(self):
        """Guards the refactor of `stops_sequence` onto the defer field."""
        result = classify(inbound(subject="Out of office", body="back monday"))
        self.assertEqual(result.verdict, Verdict.AUTOREPLY)
        self.assertFalse(result.stops_sequence)
        self.assertFalse(result.suppresses)


if __name__ == "__main__":
    unittest.main(verbosity=2)
