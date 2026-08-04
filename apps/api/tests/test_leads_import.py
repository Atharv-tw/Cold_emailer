"""Bulk import validation.

The point of these is the same one the module makes: an import must not be a
way around the checks single-add applies. So the table below is mostly the
cases where a row is *not* imported - suppressed, duplicate, addressless - and
the one soft case, a missing hook, that is surfaced without being blocked.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from app.services import leads_import  # noqa: E402
from app.services.leads_import import (  # noqa: E402
    IMPORT_PENDING_VERIFICATION,
    links_from,
    needs_import_verification,
    review,
)
from app.services.sheets import suggest_mapping  # noqa: E402


def review_of(rows, mapping=None, existing=None, suppressed=None):
    if mapping is None:
        mapping = suggest_mapping(list(rows[0].keys()), leads_import.mappable_fields())
    return review(
        rows,
        mapping,
        existing_emails=existing or set(),
        suppressed_emails=suppressed or set(),
    )


class TestMappingAliases(unittest.TestCase):
    """The alias fix `sheets` asked for: headers land on target-model fields."""

    def test_common_headers_map_to_target_fields(self):
        headers = ["Full Name", "Email Address", "Company Name", "Job Title", "LinkedIn URL", "Notes"]
        mapping = suggest_mapping(headers, leads_import.mappable_fields())
        self.assertEqual(mapping["Full Name"], "name")
        self.assertEqual(mapping["Email Address"], "email")
        self.assertEqual(mapping["Company Name"], "company")
        self.assertEqual(mapping["Job Title"], "role")
        self.assertEqual(mapping["LinkedIn URL"], "linkedin")
        self.assertEqual(mapping["Notes"], "hook")

    def test_no_header_is_mapped_to_a_dead_cli_field(self):
        # first_name / last_name / title were the old columns; nothing should
        # map onto a field the target model does not have.
        headers = ["first_name", "last_name", "e-mail", "Org"]
        mapping = suggest_mapping(headers, leads_import.mappable_fields())
        self.assertTrue(set(mapping.values()) <= set(leads_import.FIELD_KEYS))
        self.assertEqual(mapping["e-mail"], "email")
        self.assertEqual(mapping["Org"], "company")


class TestClassification(unittest.TestCase):
    def test_a_complete_row_is_ok(self):
        rows = [{"name": "Alex", "email": "alex@example.com", "hook": "their edge-batching post"}]
        result = review_of(rows)
        self.assertEqual(result.rows[0].status, "ok")
        self.assertTrue(result.rows[0].importable)

    def test_missing_hook_is_importable_but_flagged(self):
        rows = [{"name": "Alex", "email": "alex@example.com", "hook": ""}]
        row = review_of(rows).rows[0]
        self.assertEqual(row.status, "needs_hook")
        self.assertTrue(row.importable)
        self.assertTrue(any("reason" in issue for issue in row.issues))

    def test_missing_email_is_invalid(self):
        row = review_of([{"name": "Alex", "email": "", "hook": "x"}]).rows[0]
        self.assertEqual(row.status, "invalid")
        self.assertFalse(row.importable)

    def test_malformed_email_is_invalid(self):
        row = review_of([{"name": "Alex", "email": "alex@gmail", "hook": "x"}]).rows[0]
        self.assertEqual(row.status, "invalid")

    def test_suppressed_address_is_never_importable(self):
        rows = [{"name": "Alex", "email": "alex@example.com", "hook": "x"}]
        row = review_of(rows, suppressed={"alex@example.com"}).rows[0]
        self.assertEqual(row.status, "suppressed")
        self.assertFalse(row.importable)

    def test_existing_target_is_a_duplicate(self):
        rows = [{"name": "Alex", "email": "Alex@Example.com", "hook": "x"}]
        row = review_of(rows, existing={"alex@example.com"}).rows[0]
        self.assertEqual(row.status, "duplicate")

    def test_second_copy_within_the_file_is_a_duplicate(self):
        rows = [
            {"name": "Alex", "email": "alex@example.com", "hook": "x"},
            {"name": "Alex again", "email": "ALEX@example.com", "hook": "y"},
        ]
        statuses = [row.status for row in review_of(rows).rows]
        self.assertEqual(statuses, ["ok", "duplicate"])

    def test_suppression_wins_over_duplicate_and_hook(self):
        # A suppressed address is the strongest refusal; it should not be
        # reported as merely a duplicate or a missing hook.
        rows = [{"name": "Alex", "email": "alex@example.com", "hook": ""}]
        row = review_of(rows, existing={"alex@example.com"}, suppressed={"alex@example.com"}).rows[0]
        self.assertEqual(row.status, "suppressed")

    def test_email_is_normalised_on_the_row(self):
        row = review_of([{"email": "  Alex@Example.COM ", "hook": "x"}]).rows[0]
        self.assertEqual(row.email, "alex@example.com")


class TestEnumCoercion(unittest.TestCase):
    def test_known_values_pass_through(self):
        rows = [{
            "email": "a@example.com", "hook": "x",
            "target_type": "recruiter", "company_type": "fintech", "intent": "full_time",
        }]
        values = review_of(rows).rows[0].values
        self.assertEqual(values["target_type"], "recruiter")
        self.assertEqual(values["company_type"], "fintech")
        self.assertEqual(values["intent"], "full_time")

    def test_synonyms_are_understood(self):
        rows = [{
            "email": "a@example.com", "hook": "x",
            "target_type": "Co-Founder", "company_type": "Big Tech", "intent": "Full-time",
        }]
        values = review_of(rows).rows[0].values
        self.assertEqual(values["target_type"], "founder")
        self.assertEqual(values["company_type"], "faang")
        self.assertEqual(values["intent"], "full_time")

    def test_unrecognised_value_defaults_and_says_so(self):
        rows = [{"email": "a@example.com", "hook": "x", "company_type": "biotech-widgets"}]
        row = review_of(rows).rows[0]
        self.assertEqual(row.values["company_type"], "other")
        self.assertTrue(any("not recognised" in issue for issue in row.issues))
        # Still importable - a label we did not know is not a reason to drop them.
        self.assertEqual(row.status, "ok")

    def test_blank_enum_takes_the_default_silently(self):
        row = review_of([{"email": "a@example.com", "hook": "x"}]).rows[0]
        self.assertEqual(row.values["intent"], "internship")
        self.assertFalse(any("not recognised" in issue for issue in row.issues))


class TestSummaryAndLinks(unittest.TestCase):
    def test_summary_counts_each_bucket(self):
        rows = [
            {"email": "ok@example.com", "hook": "x"},           # ok
            {"email": "nohook@example.com", "hook": ""},        # needs_hook
            {"email": "dupe@example.com", "hook": "x"},         # duplicate (existing)
            {"email": "bad@gmail", "hook": "x"},                # invalid
            {"email": "stop@example.com", "hook": "x"},         # suppressed
        ]
        result = review_of(
            rows, existing={"dupe@example.com"}, suppressed={"stop@example.com"}
        )
        s = result.summary()
        self.assertEqual(s["total"], 5)
        self.assertEqual(s["importable"], 2)  # ok + needs_hook
        self.assertEqual(s["needs_hook"], 1)
        self.assertEqual(s["duplicates"], 1)
        self.assertEqual(s["invalid"], 1)
        self.assertEqual(s["suppressed"], 1)

    def test_unmapped_required_email_is_reported(self):
        rows = [{"name": "Alex", "company": "Acme"}]
        result = review_of(rows, mapping={"name": "name", "company": "company"})
        self.assertIn("email", result.unmapped_required)

    def test_links_are_folded_from_their_columns(self):
        rows = [{
            "email": "a@example.com", "hook": "x",
            "linkedin": "https://linkedin.com/in/alex", "github": "  ", "portfolio": "alex.dev",
        }]
        links = links_from(review_of(rows).rows[0].values)
        self.assertEqual(links, {"linkedin": "https://linkedin.com/in/alex", "portfolio": "alex.dev"})


class TestDeferredVerification(unittest.TestCase):
    def test_imported_targets_are_flagged_for_later_verification(self):
        self.assertTrue(needs_import_verification(IMPORT_PENDING_VERIFICATION))

    def test_a_checked_address_does_not_re_trigger(self):
        self.assertFalse(needs_import_verification({"status": "deliverable", "reason": "accepted_email"}))
        self.assertFalse(needs_import_verification({"status": "undeliverable", "reason": "invalid"}))

    def test_a_target_with_no_verification_is_not_treated_as_import_pending(self):
        # Manually-added targets always carry a real verification; an empty one
        # must not accidentally trip the import-only lazy check.
        self.assertFalse(needs_import_verification({}))
        self.assertFalse(needs_import_verification(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
