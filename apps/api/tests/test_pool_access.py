"""The entitlement gate on the shared pool.

Two different things are worth asserting here, and only one of them is about
the check itself.

The first is that an unpaid account is refused - trivial, but it is the whole
product boundary.

The second is that **every** route on the pool router goes through the gate.
The listing is what a browser hits, so a missing check there would be noticed
immediately; `add_from_pool` is a POST that no unpaid user's UI ever renders,
so a missing check there would be invisible until somebody found it. That
asymmetry is exactly why it gets a test that does not depend on anyone
remembering to write one for the next endpoint either.

No database: the gate reads one boolean off the user, and the routes' wiring is
a property of the source.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from fastapi import HTTPException  # noqa: E402

from app.routers import pool  # noqa: E402


class FakeUser:
    def __init__(self, is_paid: bool) -> None:
        self.is_paid = is_paid


class TestRequirePoolAccess(unittest.TestCase):
    def test_an_unpaid_account_is_refused_with_402(self):
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(pool.require_pool_access(FakeUser(is_paid=False)))

        # 402, not 403: they are authenticated and permitted in principle. The
        # web app distinguishes the two - one is an upsell, the other is a bug.
        self.assertEqual(caught.exception.status_code, 402)

    def test_a_paid_account_passes(self):
        self.assertIsNone(asyncio.run(pool.require_pool_access(FakeUser(is_paid=True))))


class TestEveryPoolRouteIsGated(unittest.TestCase):
    def test_no_route_on_the_pool_router_skips_the_gate(self):
        """Catches an endpoint added later that forgets to call the gate.

        Reads the registered routes rather than a hand-written list, so a new
        one is covered the moment it exists. The failure this prevents is a
        pool endpoint that quietly serves shared contacts to accounts that did
        not pay for them - which nothing else in the suite would notice.
        """
        checked = []
        for route in pool.router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            source = inspect.getsource(endpoint)
            checked.append(endpoint.__name__)
            self.assertIn(
                "require_pool_access",
                source,
                f"{endpoint.__name__} does not call require_pool_access",
            )

        # Guards the guard: if the router is ever restructured so this loop
        # finds nothing, the assertions above would all pass vacuously.
        self.assertGreaterEqual(len(checked), 2, f"expected pool routes, found {checked}")


if __name__ == "__main__":
    unittest.main()
