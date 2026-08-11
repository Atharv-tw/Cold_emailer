"""The codes attached to refusals.

The web app branches on these - `profile_incomplete` opens the modal that
links to the profile rather than printing a sentence under a form - so a
misspelled or invented code does not fail here, it fails as a modal that
silently stops appearing. Hence a test that reads the source: any name used as
`errors.SOMETHING` has to be a constant that exists.

The shape is asserted too. FastAPI serialises `detail` as it is given, so a
refusal reaches the browser as `{"detail": {"code": ..., "message": ...}}`,
and `lib/api.ts` reads exactly that.
"""

from __future__ import annotations

import asyncio
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from app import errors  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.routers import pool  # noqa: E402

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"


class TestAppError(unittest.TestCase):
    def test_the_detail_is_the_code_and_the_message(self):
        error = AppError(409, errors.DUPLICATE_TARGET, "They are already on your list.")

        self.assertEqual(
            error.detail, {"code": "duplicate_target", "message": "They are already on your list."}
        )
        self.assertEqual(error.status_code, 409)

    def test_a_refusal_carries_its_code(self):
        class Unpaid:
            is_paid = False

        with self.assertRaises(AppError) as caught:
            asyncio.run(pool.require_pool_access(Unpaid()))

        self.assertEqual(caught.exception.code, errors.POOL_ACCESS_REQUIRED)


class TestEveryCodeExists(unittest.TestCase):
    def test_no_router_names_a_code_that_was_never_defined(self):
        used = set()
        for path in ROUTERS.glob("*.py"):
            used.update(re.findall(r"\berrors\.([A-Z_]+)\b", path.read_text(encoding="utf-8")))

        missing = sorted(name for name in used if not hasattr(errors, name))
        self.assertEqual(missing, [], f"undefined error codes: {missing}")

        # Guards the guard: a refactor that moves every raise out of the
        # routers would otherwise leave this passing on an empty set.
        self.assertGreaterEqual(len(used), 5, f"expected codes in use, found {sorted(used)}")


if __name__ == "__main__":
    unittest.main()
