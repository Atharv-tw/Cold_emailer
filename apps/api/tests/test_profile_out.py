"""Everything a user typed comes back when the profile is read.

`_out` builds its projects and experience by hand, field by field, into dicts.
`ProjectOut` and `ExperienceOut` give every field a default, so a field left out
of those literals does not raise - it returns empty. The form then renders a
blank box, and the value looks like it was never saved while it sits in the
database untouched.

That is what happened to `demo_url`: migration 0006 added the column, the model
carried it, `ProjectIn` declared it and the write path stored it, but the
serialiser's dict never mentioned it. Nothing failed anywhere.

So rather than checking one field, these set every field to a distinctive value
and assert it survives the round trip. A column added later that nobody wires
into `_out` fails here instead of being reported as a bug months on.

No database: `_out` takes plain objects.
"""

from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from app.routers.profile import _out  # noqa: E402
from app.schemas import ExperienceIn, ProjectIn  # noqa: E402


class Fake:
    """Anything, with the attributes it was handed."""

    def __init__(self, **attrs) -> None:
        self.__dict__.update(attrs)


def _fake_profile() -> Fake:
    return Fake(
        headline="Builds things",
        bio="A bio",
        education="A degree",
        availability="Immediately",
        links={"github": "https://example.com"},
        sending_window={},
        daily_cap=20,
    )


def _fake_project() -> Fake:
    """One project with every `ProjectIn` field set to something recognisable."""
    return Fake(
        id=uuid.uuid4(),
        name="name-value",
        summary="summary-value",
        tech="tech-value",
        url="https://url-value",
        demo_url="https://demo-url-value",
        highlights=["highlight-value"],
        categories=["category-value"],
        best_for=["best-for-value"],
        position=0,
    )


def _fake_experience() -> Fake:
    return Fake(
        id=uuid.uuid4(),
        company="company-value",
        role="role-value",
        started="started-value",
        ended="ended-value",
        bullets=["bullet-value"],
        position=0,
    )


class TestProjectsSurviveSerialisation(unittest.TestCase):
    def test_every_ProjectIn_field_comes_back(self):
        source = _fake_project()
        out = _out(_fake_profile(), [source], [])

        self.assertEqual(len(out.projects), 1)
        project = out.projects[0]

        for field in ProjectIn.model_fields:
            self.assertEqual(
                getattr(project, field),
                getattr(source, field),
                f"`{field}` is declared on ProjectIn but _out does not carry it "
                f"through - it will silently read back empty",
            )

    def test_demo_url_specifically(self):
        """The field this test file exists because of."""
        out = _out(_fake_profile(), [_fake_project()], [])
        self.assertEqual(out.projects[0].demo_url, "https://demo-url-value")


class TestExperienceSurvivesSerialisation(unittest.TestCase):
    def test_every_ExperienceIn_field_comes_back(self):
        source = _fake_experience()
        out = _out(_fake_profile(), [], [source])

        self.assertEqual(len(out.experience), 1)
        experience = out.experience[0]

        for field in ExperienceIn.model_fields:
            self.assertEqual(
                getattr(experience, field),
                getattr(source, field),
                f"`{field}` is declared on ExperienceIn but _out does not carry "
                f"it through",
            )


if __name__ == "__main__":
    unittest.main()
