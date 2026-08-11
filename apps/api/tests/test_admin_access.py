"""The two properties that make an admin panel safe to have at all.

Neither is about a feature working. Both are about a failure that would be
silent: a route that forgets its guard serves cross-account data to anybody,
and a body model that accepts `is_admin` turns "signed in" into "operator" for
anyone who reads the OpenAPI schema.

No database. Both are properties of the wiring, which is where the mistake
would be.
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

from app.deps import admin_user  # noqa: E402
from app.routers import admin  # noqa: E402


class FakeUser:
    def __init__(self, is_admin: bool) -> None:
        self.is_admin = is_admin


class FakeSession:
    """Records whether the session was elevated, and nothing else."""

    def __init__(self) -> None:
        self.elevated = False
        self.sync_session = self

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    async def execute(self, *_args, **_kwargs):
        self.elevated = True
        return None

    @property
    def info(self) -> dict:
        return self.__dict__.setdefault("_info", {})


class TestAdminDependency(unittest.TestCase):
    def test_a_normal_account_is_refused(self):
        session = FakeSession()
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(admin_user(FakeUser(is_admin=False), session))
        self.assertEqual(caught.exception.status_code, 403)

    def test_a_refused_account_never_elevates_the_session(self):
        """The refusal has to happen before the elevation, not beside it.

        `app.is_admin` widens the `users` policies added in 0011, so setting it
        for a session that then goes on to serve an ordinary request would hand
        that request every account on the platform.
        """
        session = FakeSession()
        with self.assertRaises(HTTPException):
            asyncio.run(admin_user(FakeUser(is_admin=False), session))
        self.assertFalse(session.elevated)

    def test_an_operator_passes_through_and_elevates(self):
        user = FakeUser(is_admin=True)
        session = FakeSession()
        self.assertIs(asyncio.run(admin_user(user, session)), user)
        # Without this the panel reads its own row and nothing else - which is
        # not an error, just an empty list, which is how it went unnoticed.
        self.assertTrue(session.elevated)


class TestEveryAdminRouteIsGuarded(unittest.TestCase):
    def test_no_route_on_the_admin_router_skips_AdminUser(self):
        """Catches a route added later that forgets the guard.

        Reads the registered routes rather than a hand-written list, so the
        next endpoint is covered before anyone remembers to test it. Every
        handler here reads or writes across accounts, so an unguarded one is
        not a smaller version of the same bug - it is the whole boundary gone.
        """
        checked = []
        for route in admin.router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            checked.append(endpoint.__name__)
            self.assertIn(
                "AdminUser",
                inspect.getsource(endpoint),
                f"{endpoint.__name__} is not behind AdminUser",
            )

        self.assertGreaterEqual(len(checked), 7, f"expected admin routes, found {checked}")


class TestNoRouteCanGrantTheRole(unittest.TestCase):
    def test_the_plan_body_cannot_carry_is_admin(self):
        """`is_admin` must not be reachable from a request body.

        pydantic ignores undeclared fields, so passing it is not an error - it
        is simply dropped. Asserting that explicitly is the point: it is what
        makes "no code path from signed-in to privileged" true rather than
        merely intended.
        """
        payload = admin.PlanIn(**{"is_paid": True, "is_admin": True})
        self.assertTrue(payload.is_paid)
        self.assertFalse(hasattr(payload, "is_admin"))

    def test_no_request_model_on_the_admin_router_declares_is_admin(self):
        for name in dir(admin):
            candidate = getattr(admin, name)
            fields = getattr(candidate, "model_fields", None)
            if not isinstance(fields, dict):
                continue
            # Output models may report it - the panel has to render who is an
            # operator. Only inbound bodies are the risk.
            if name.endswith("In"):
                self.assertNotIn("is_admin", fields, f"{name} accepts is_admin")

    def test_the_admin_source_never_assigns_is_admin(self):
        """Belt and braces: nothing here writes the column, whatever the shape.

        A future handler could set it from something other than a body - a
        query parameter, a copied user object - and the model check above would
        not see that.
        """
        source = inspect.getsource(admin)
        self.assertNotIn("is_admin =", source)
        self.assertNotIn("is_admin=True", source)


if __name__ == "__main__":
    unittest.main()
