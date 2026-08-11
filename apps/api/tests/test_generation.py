"""Prompt assembly and draft parsing.

The prompt is the product here, so these tests assert what is in it. The
rules that came over from the CLI are load-bearing - drop the "never invent
facts" line and the model will happily tell a stranger you admired a paper
they did not write.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from app.services.generation import (  # noqa: E402
    build_prompt, ranked_projects, recipient_block, sender_block, split_subject,
)
from app.services.playbooks import (  # noqa: E402
    FIRST_TOUCH_RULES, FOLLOW_UP_RULES, LAST_TOUCH_RULES, TARGET_PLAYBOOKS,
    playbook_for, touch_rules,
)


def profile():
    return SimpleNamespace(
        headline="Backend engineer, distributed systems",
        bio="Works on ingest pipelines.",
        education="BSc Computer Science",
        availability="From June",
        links={"github": "github.com/dana"},
    )


def target(**overrides):
    base = dict(
        name="Alex Chen",
        role="Founder",
        company="ExampleCorp",
        company_type="ai",
        target_type="founder",
        intent="internship",
        hook="your post on cutting inference cost by batching at the edge",
        links={"linkedin": "linkedin.com/in/alexchen"},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def projects():
    return [
        SimpleNamespace(
            name="ratelimit",
            summary="token bucket library",
            tech="Rust",
            url="github.com/dana/ratelimit",
            categories=["infra"],
            best_for=["engineer"],
            position=0,
        )
    ]


def experience():
    return [
        SimpleNamespace(
            company="ExampleCorp", role="Engineer", started="2023", ended="",
            bullets=["Cut p99 from 800ms to 90ms"],
        )
    ]


def prompt(**overrides) -> str:
    kwargs = dict(
        profile=profile(), projects=projects(), experience=experience(),
        target=target(), step=1,
    )
    kwargs.update(overrides)
    return build_prompt(**kwargs)


class TestPromptRules(unittest.TestCase):
    def test_hard_rules_carry_over_from_the_cli(self):
        text = prompt()
        for rule in (
            "Plain text only",
            "At most one URL",
            "Under 900 characters",
            "Never invent facts about the recipient",
        ):
            self.assertIn(rule, text, rule)

    def test_the_hook_is_in_the_prompt(self):
        # The one thing the model could not have guessed.
        self.assertIn("batching at the edge", prompt())

    def test_sender_profile_reaches_the_prompt(self):
        text = prompt()
        self.assertIn("Backend engineer", text)
        self.assertIn("ratelimit", text)
        self.assertIn("Cut p99", text)

    def test_missing_hook_is_named_rather_than_papered_over(self):
        text = prompt(target=target(hook=""))
        self.assertIn("did not say what made them pick this person", text)
        self.assertIn("Do not invent a reason", text)

    def test_playbook_matches_the_recipient_type(self):
        founder = prompt(target=target(target_type="founder"))
        professor = prompt(target=target(target_type="professor"))
        self.assertIn("Founders read their own inbox", founder)
        self.assertIn("read the work", professor)
        self.assertNotIn("Founders read their own inbox", professor)

    def test_every_target_type_has_a_playbook(self):
        for kind in ("founder", "hiring_manager", "recruiter", "engineer", "professor"):
            self.assertIn(kind, TARGET_PLAYBOOKS)
            self.assertGreater(len(playbook_for(kind)), 100)

    def test_unknown_type_falls_back_rather_than_failing(self):
        self.assertIn("individual", playbook_for("astronaut"))

    def test_intent_is_stated(self):
        self.assertIn("internship", prompt(target=target(intent="internship")).lower())

    def test_company_context_is_included(self):
        self.assertIn("generic AI email", prompt(target=target(company_type="ai")))

    def test_instruction_overrides_and_is_labelled_as_such(self):
        text = prompt(instruction="mention the latency work")
        self.assertIn("mention the latency work", text)
        self.assertIn("overrides the style guidance", text)

    def test_selected_template_reaches_the_prompt(self):
        text = prompt(template_key="project_fit")
        self.assertIn("Selected template: Project fit", text)
        self.assertIn("most relevant project", text)

    def test_project_metadata_reaches_the_prompt(self):
        text = prompt()
        self.assertIn("best for: engineer", text)
        self.assertIn("github.com/dana/ratelimit", text)

    def test_projects_are_ranked_against_target_context(self):
        ranked = ranked_projects(
            [
                SimpleNamespace(
                    name="generic",
                    summary="generic website",
                    tech="React",
                    categories=["frontend"],
                    best_for=["recruiter"],
                    position=0,
                ),
                SimpleNamespace(
                    name="inference",
                    summary="batched inference service",
                    tech="Python",
                    categories=["ai"],
                    best_for=["founder"],
                    position=1,
                ),
            ],
            target(company_type="ai", target_type="founder"),
        )
        self.assertEqual(ranked[0].name, "inference")


class TestFirstEmailShape(unittest.TestCase):
    def test_the_first_email_asks_for_three_paragraphs(self):
        text = prompt(step=1)
        self.assertIn("three paragraphs and nothing else", text)
        for role in ("1. Intro", "2. The work", "3. The ask"):
            self.assertIn(role, text, role)

    def test_the_shape_is_stated_briefly(self):
        # The first draft of this block spelled out what each paragraph was
        # for, and the model answered in kind - dense, over-explained mail.
        # Terse instructions are the whole point, so the length is asserted.
        self.assertLess(len(FIRST_TOUCH_RULES), 500)

    def test_the_shape_does_not_leak_into_follow_ups(self):
        # A follow-up is two or three sentences; three paragraphs would be
        # the pitch all over again, which is what nobody replies to.
        for step in (2, 3):
            text = prompt(step=step, thread=[("Subject", "Body")])
            self.assertNotIn("three paragraphs and nothing else", text)
            self.assertIn("does not apply", text)

    def test_templates_steer_within_the_shape_rather_than_replacing_it(self):
        for key in ("specific_hook", "project_fit", "recruiter_scan", "research_interest"):
            text = prompt(template_key=key)
            self.assertIn("three paragraphs", text, key)
            self.assertNotIn("Structure:", text, key)


class TestFollowUps(unittest.TestCase):
    def test_first_touch_says_they_have_never_heard_from_you(self):
        self.assertIn("never heard from you", touch_rules(1, 3))
        self.assertEqual(touch_rules(1, 3), FIRST_TOUCH_RULES)

    def test_middle_touch_gets_the_follow_up_rules(self):
        self.assertEqual(touch_rules(2, 3), FOLLOW_UP_RULES)

    def test_last_touch_says_it_is_the_last(self):
        self.assertEqual(touch_rules(3, 3), LAST_TOUCH_RULES)
        self.assertIn("nothing further will be sent", LAST_TOUCH_RULES)

    def test_follow_up_forbids_the_usual_filler(self):
        for phrase in ("just following up", "bumping this", "circling back"):
            self.assertIn(phrase, FOLLOW_UP_RULES)

    def test_follow_up_must_not_repeat_what_was_already_sent(self):
        text = prompt(
            step=2,
            thread=[("Hi Alex - inference cost", "The first email, already sent.")],
        )
        self.assertIn("already sent", text)
        self.assertIn("Do not repeat anything in them", text)
        self.assertIn("The first email, already sent.", text)

    def test_first_email_carries_no_thread(self):
        self.assertNotIn("already sent", prompt(step=1))


class TestSplitSubject(unittest.TestCase):
    def test_pulls_the_subject_off_the_front(self):
        subject, body = split_subject("Subject: Inference cost\n\nHi Alex,\n\nI read your post.")
        self.assertEqual(subject, "Inference cost")
        self.assertTrue(body.startswith("Hi Alex,"))

    def test_missing_subject_leaves_the_body_intact(self):
        subject, body = split_subject("Hi Alex,\n\nI read your post.")
        self.assertEqual(subject, "")
        self.assertTrue(body.startswith("Hi Alex,"))

    def test_subject_further_down_is_still_found(self):
        subject, _ = split_subject("\n\nSubject: Late\n\nBody")
        self.assertEqual(subject, "Late")

    def test_a_subject_line_in_the_body_is_not_mistaken_for_the_header(self):
        _, body = split_subject("Subject: Real\n\nHi,\n\nSubject: not a header\n")
        self.assertIn("Subject: not a header", body)


class TestBlocks(unittest.TestCase):
    def test_empty_sections_say_so_rather_than_going_blank(self):
        empty = SimpleNamespace(headline="", bio="", education="", availability="", links={})
        self.assertIn("(nothing supplied)", sender_block(empty, [], []))

    def test_recipient_block_omits_empty_fields(self):
        block = recipient_block(target(company="", role=""))
        self.assertNotIn("company:", block)
        self.assertIn("Alex Chen", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
