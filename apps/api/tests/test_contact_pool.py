"""The pure half of the pool loader: flattening and the derived fields.

The writing half needs a BYPASSRLS role and is exercised by running the script;
everything here is a function of the source data alone, which is where the
mistakes that would silently mis-file 499 contacts actually live.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "core"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from load_contact_pool import (  # noqa: E402
    company_type_for,
    domains_agree,
    flatten,
    host_of,
    target_type_for,
    timezone_for,
)


def startup(name="Aztech", employees=None, **overrides) -> dict:
    return {
        "name": name,
        "description": "Does a thing",
        "website": "https://aztech.com",
        "sector": "AI",
        "location": "Bengaluru",
        "startup_employees": employees or [],
        **overrides,
    }


def employee(email="alex@aztech.com", **overrides) -> dict:
    return {
        "id": f"src-{email}",
        "name": "Alex",
        "role": "Co-founder",
        "email": email,
        "linkedin_url": "https://linkedin.com/in/alex",
        **overrides,
    }


class TestTargetType(unittest.TestCase):
    def test_every_founder_spelling_collapses_to_one_value(self):
        for role in (
            "Co-founder", "Co-Founder", "CoFounder", "Cofounder", "Founder",
            "CEO", "CTO", "COO", "Founder & CEO", "Co-Founder & CEO",
            "Founder's Office",
        ):
            self.assertEqual(target_type_for(role), "founder", role)

    def test_hr_is_a_hiring_manager(self):
        self.assertEqual(target_type_for("HR"), "hiring_manager")
        self.assertEqual(target_type_for("Recruiter"), "hiring_manager")

    def test_the_long_tail_defaults_to_founder(self):
        """A list of startup founders should not be full of empty enums."""
        for role in ("", "-", "Product", "something unexpected"):
            self.assertEqual(target_type_for(role), "founder", repr(role))

    def test_matching_ignores_case_and_padding(self):
        self.assertEqual(target_type_for("  ceo  "), "founder")


class TestCompanyType(unittest.TestCase):
    def test_real_sectors_map_across(self):
        self.assertEqual(company_type_for("AI"), "ai")
        self.assertEqual(company_type_for("FinTech"), "fintech")
        self.assertEqual(company_type_for("EdTech"), "edtech")

    def test_trailing_whitespace_does_not_split_a_bucket(self):
        """The export contains both "AI" and "AI " - 66 rows and 8."""
        self.assertEqual(company_type_for("AI "), company_type_for("AI"))

    def test_curation_buckets_are_not_sectors(self):
        for bucket in ("Trending", "Core", "YC", "Shark Tank", "Community"):
            self.assertEqual(company_type_for(bucket), "other", bucket)

    def test_unmapped_real_sectors_fall_through_to_other(self):
        for sector in ("Healthcare", "Food", "FashionTech"):
            self.assertEqual(company_type_for(sector), "other", sector)


class TestTimezone(unittest.TestCase):
    def test_every_indian_spelling_lands_in_one_zone(self):
        for location in (
            "Bengaluru", "Bengaluru, Karnataka", "Bengaluru, India",
            "Bangalore, India", "Mumbai", "Gurugram", "New Delhi", "India",
            "India-wide", "",
        ):
            self.assertEqual(timezone_for(location), "Asia/Kolkata", location)

    def test_us_locations_are_not_swept_into_the_default(self):
        self.assertEqual(timezone_for("San Francisco"), "America/Los_Angeles")


class TestDomainAgreement(unittest.TestCase):
    def test_host_is_stripped_of_scheme_and_www(self):
        self.assertEqual(host_of("https://www.Trupeer.ai/pricing"), "trupeer.ai")

    def test_matching_domains_agree(self):
        self.assertTrue(domains_agree("aztech.com", "aztech.com"))

    def test_subdomains_agree(self):
        self.assertTrue(domains_agree("mail.aztech.com", "aztech.com"))

    def test_a_transcription_error_disagrees(self):
        """The real case from the source data: a dropped letter."""
        self.assertFalse(domains_agree("putope.io", "plutope.io"))

    def test_no_website_cannot_disagree(self):
        self.assertTrue(domains_agree("aztech.com", ""))


class TestFlatten(unittest.TestCase):
    def test_company_fields_are_denormalised_onto_each_person(self):
        rows = flatten([startup(employees=[employee(), employee("alan@aztech.com")])])
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["company"], "Aztech")
            self.assertEqual(row["company_description"], "Does a thing")
            self.assertEqual(row["company_website"], "https://aztech.com")

    def test_a_repeated_address_is_kept_once(self):
        """The export lists 8 people under two companies each."""
        rows = flatten([
            startup(employees=[employee()]),
            startup(name="Other Co", employees=[employee()]),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company"], "Aztech")  # first occurrence wins

    def test_addresses_are_normalised(self):
        rows = flatten([startup(employees=[employee("  Alex@AZTECH.com ")])])
        self.assertEqual(rows[0]["email"], "alex@aztech.com")

    def test_rows_without_a_usable_address_are_dropped(self):
        rows = flatten([startup(employees=[
            employee(email=""),
            employee(email="not-an-address"),
            employee(email="fine@aztech.com"),
        ])])
        self.assertEqual([row["email"] for row in rows], ["fine@aztech.com"])

    def test_linkedin_becomes_a_link_and_absence_leaves_it_empty(self):
        rows = flatten([startup(employees=[
            employee(),
            employee("b@aztech.com", linkedin_url=""),
        ])])
        self.assertEqual(rows[0]["links"], {"linkedin": "https://linkedin.com/in/alex"})
        self.assertEqual(rows[1]["links"], {})

    def test_source_id_is_carried_so_reloads_are_idempotent(self):
        rows = flatten([startup(employees=[employee()])])
        self.assertEqual(rows[0]["source_id"], "src-alex@aztech.com")

    def test_a_startup_with_no_employees_contributes_nothing(self):
        self.assertEqual(flatten([startup(employees=[])]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
