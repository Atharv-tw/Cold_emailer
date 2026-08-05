"""The calendar reminder layer.

Two things are worth testing without a real calendar behind them: the HTTP
client's mapping of Google's status codes onto our error types (a revoked grant
must stop the sync, a rate limit must not be mistaken for one), and the pure
transition table that decides what the calendar needs for a given schedule row.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from app.services.calendar_sync import plan_action  # noqa: E402
from app.services.google_calendar import (  # noqa: E402
    EVENT_LENGTH,
    CalendarAuthRevoked,
    CalendarClient,
    CalendarError,
    CalendarNotFound,
    build_event_body,
)


def client_for(handler) -> CalendarClient:
    return CalendarClient(access_token="t", transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


class TestClientRequests(unittest.TestCase):
    def test_create_returns_the_event_id(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            return httpx.Response(200, json={"id": "evt_123"})

        event_id = run(client_for(handler).create_event({"summary": "x"}))
        self.assertEqual(event_id, "evt_123")
        self.assertEqual(captured["method"], "POST")
        self.assertTrue(captured["path"].endswith("/calendars/primary/events"))

    def test_update_patches_the_event(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            return httpx.Response(200, json={"id": "evt_123"})

        run(client_for(handler).update_event("evt_123", {"summary": "y"}))
        self.assertEqual(captured["method"], "PATCH")
        self.assertTrue(captured["path"].endswith("/events/evt_123"))

    def test_delete_treats_already_gone_as_success(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(410, json={"error": {"message": "deleted"}})

        # Must not raise: the reminder is gone, which is the goal.
        run(client_for(handler).delete_event("evt_123"))


class TestClientErrorMapping(unittest.TestCase):
    def _raises(self, status_code: int, body: dict, exc):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code, json=body)

        with self.assertRaises(exc):
            run(client_for(handler).create_event({}))

    def test_401_is_auth_revoked(self):
        self._raises(401, {"error": {"message": "bad creds"}}, CalendarAuthRevoked)

    def test_403_without_scope_is_auth_revoked(self):
        self._raises(403, {"error": {"message": "insufficient permission"}}, CalendarAuthRevoked)

    def test_403_rate_limit_is_retryable_not_auth(self):
        def handler(_request):
            return httpx.Response(403, json={"error": {"message": "userRateLimitExceeded"}})

        with self.assertRaises(CalendarError) as ctx:
            run(client_for(handler).create_event({}))
        self.assertNotIsInstance(ctx.exception, CalendarAuthRevoked)

    def test_404_is_not_found(self):
        self._raises(404, {"error": {"message": "no such event"}}, CalendarNotFound)

    def test_500_is_a_plain_error(self):
        self._raises(500, {"error": {"message": "boom"}}, CalendarError)


class TestEventBody(unittest.TestCase):
    def test_body_has_a_fifteen_minute_window_and_a_link(self):
        when = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        body = build_event_body(
            title="Follow up with Alex",
            when=when,
            description="Company: Acme",
            url="https://app.example.com/targets/abc",
        )
        self.assertEqual(body["summary"], "Follow up with Alex")
        self.assertEqual(body["start"]["dateTime"], when.isoformat())
        self.assertEqual(body["end"]["dateTime"], (when + EVENT_LENGTH).isoformat())
        self.assertEqual(body["source"]["url"], "https://app.example.com/targets/abc")
        self.assertEqual(body["reminders"], {"useDefault": True})

    def test_no_source_without_a_url(self):
        body = build_event_body(title="t", when=datetime.now(timezone.utc), description="d")
        self.assertNotIn("source", body)


class TestPlanAction(unittest.TestCase):
    """The one-directional transition table: the row is truth, the event a copy."""

    def setUp(self):
        self.due = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)

    def test_pending_without_event_creates(self):
        self.assertEqual(
            plan_action(state="pending", due_at=self.due, google_event_id="", event_synced_due_at=None),
            "create",
        )

    def test_pending_in_sync_does_nothing(self):
        self.assertEqual(
            plan_action(
                state="pending", due_at=self.due, google_event_id="e", event_synced_due_at=self.due
            ),
            "none",
        )

    def test_moved_due_date_updates(self):
        moved = self.due + timedelta(days=2)
        self.assertEqual(
            plan_action(
                state="pending", due_at=moved, google_event_id="e", event_synced_due_at=self.due
            ),
            "update",
        )

    def test_cancelled_row_with_event_deletes(self):
        self.assertEqual(
            plan_action(state="cancelled", due_at=self.due, google_event_id="e", event_synced_due_at=self.due),
            "delete",
        )

    def test_sent_row_with_event_deletes(self):
        # A sent touch's row becomes "done"; its reminder is now stale.
        self.assertEqual(
            plan_action(state="done", due_at=self.due, google_event_id="e", event_synced_due_at=self.due),
            "delete",
        )

    def test_terminal_row_that_never_had_an_event_does_nothing(self):
        self.assertEqual(
            plan_action(state="cancelled", due_at=self.due, google_event_id="", event_synced_due_at=None),
            "none",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
