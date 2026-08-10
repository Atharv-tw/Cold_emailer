"""The Gmail transport, and reading replies out of it.

This is the fake-transport integration the plan called for, mirroring the old
FakeSMTP: real MIME construction, real threading headers, real Gmail response
shapes, no network. The two behaviours worth breaking a build over are here -
threading across three touches, and an out-of-office deferring rather than
stopping a sequence.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from outreach_core.mime import Outgoing, SenderIdentity, build_message  # noqa: E402

from app.services.gmail import (  # noqa: E402
    GmailAuthRevoked, GmailClient, GmailError, GmailNotFound, GmailRateLimited,
    exchange_refresh_token,
)
from app.services.replies import (  # noqa: E402
    delivery_status, headers_of, plain_text, process_thread,
)

SENDER = SenderIdentity(email="me@send.test", from_name="Dana Sharma")


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


class FakeGmail:
    """Records what would go out, and answers like Gmail does.

    Notably it assigns its own Message-ID, because Gmail does, and code that
    threads against a Message-ID it set itself would pass a weaker test.
    """

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.threads: dict[str, dict] = {}
        self.messages: dict[str, dict] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path.endswith("/messages/send"):
            payload = json.loads(request.content)
            raw = base64.urlsafe_b64decode(payload["raw"] + "=" * (-len(payload["raw"]) % 4))
            index = len(self.sent) + 1
            message_id = f"<gmail-{index}@mail.gmail.com>"
            thread_id = payload.get("threadId") or "thread-1"
            self.sent.append(
                {"raw": raw.decode("utf-8", "replace"), "threadId": payload.get("threadId")}
            )
            self.messages[f"m{index}"] = {
                "payload": {"headers": [{"name": "Message-ID", "value": message_id}]}
            }
            return httpx.Response(200, json={"id": f"m{index}", "threadId": thread_id})

        if "/messages/" in path:
            message_id = path.rsplit("/", 1)[-1]
            if message_id not in self.messages:
                return httpx.Response(404, json={"error": {"message": "not found"}})
            return httpx.Response(200, json=self.messages[message_id])

        if "/threads/" in path:
            thread_id = path.rsplit("/", 1)[-1]
            if thread_id not in self.threads:
                return httpx.Response(404, json={"error": {"message": "not found"}})
            return httpx.Response(200, json=self.threads[thread_id])

        return httpx.Response(200, json={})

    def client(self) -> GmailClient:
        return GmailClient("token", transport=httpx.MockTransport(self.handler))

    def add_inbound(self, thread_id: str, *, headers: dict, body: str, from_user: bool = False):
        message_id = f"in{len(self.messages) + 1}"
        payload = {
            "headers": [{"name": name, "value": value} for name, value in headers.items()],
            "mimeType": "text/plain",
            "body": {"data": b64(body)},
        }
        self.messages[message_id] = {"id": message_id, "payload": payload}
        thread = self.threads.setdefault(thread_id, {"id": thread_id, "messages": []})
        thread["messages"].append({"id": message_id, "payload": payload})
        return message_id


class TestSending(unittest.TestCase):
    def test_send_payload_is_base64url_rfc822(self):
        gmail = FakeGmail()
        message = build_message(SENDER, Outgoing("alex@example.com", "Hi Alex", "Body text"))
        result = asyncio.run(gmail.client().send(message))

        self.assertEqual(len(gmail.sent), 1)
        raw = gmail.sent[0]["raw"]
        self.assertIn("To: alex@example.com", raw)
        self.assertIn("Subject: Hi Alex", raw)
        self.assertIn("From: Dana Sharma <me@send.test>", raw)
        self.assertEqual(result.gmail_message_id, "m1")

    def test_message_id_is_read_back_from_gmail_not_assumed(self):
        gmail = FakeGmail()
        message = build_message(SENDER, Outgoing("alex@example.com", "Hi", "Body"))
        result = asyncio.run(gmail.client().send(message))
        self.assertEqual(result.rfc822_message_id, "<gmail-1@mail.gmail.com>")
        # Nothing we set - the outgoing message carried no Message-ID at all.
        self.assertNotIn("Message-ID:", gmail.sent[0]["raw"])

    def test_thread_id_is_passed_through_for_follow_ups(self):
        gmail = FakeGmail()
        asyncio.run(
            gmail.client().send(
                build_message(SENDER, Outgoing("alex@example.com", "Re: Hi", "Body")),
                "thread-42",
            )
        )
        self.assertEqual(gmail.sent[0]["threadId"], "thread-42")

    def test_three_touches_thread_correctly(self):
        gmail = FakeGmail()
        client = gmail.client()
        references = ""
        last = None
        thread_id = None

        for touch in range(3):
            subject = "Hi Alex - inference cost" if touch == 0 else "Re: Hi Alex - inference cost"
            message = build_message(
                SENDER,
                Outgoing(
                    to_email="alex@example.com",
                    subject=subject,
                    body=f"Touch {touch + 1}",
                    in_reply_to=last,
                    references=references,
                ),
            )
            result = asyncio.run(client.send(message, thread_id))
            thread_id = result.thread_id
            last = result.rfc822_message_id
            references = f"{references} {last}".strip()

        first, second, third = (item["raw"] for item in gmail.sent)
        self.assertNotIn("In-Reply-To:", first)
        self.assertIn("In-Reply-To: <gmail-1@mail.gmail.com>", second)
        self.assertIn("In-Reply-To: <gmail-2@mail.gmail.com>", third)
        # References accumulates the whole chain, not just the parent.
        self.assertIn("<gmail-1@mail.gmail.com>", third)
        self.assertIn("<gmail-2@mail.gmail.com>", third)
        self.assertTrue(second.count("Subject: Re: ") == 1)

    def test_personal_mail_carries_no_list_unsubscribe(self):
        gmail = FakeGmail()
        asyncio.run(
            gmail.client().send(build_message(SENDER, Outgoing("a@b.com", "Hi", "Body")))
        )
        self.assertNotIn("List-Unsubscribe", gmail.sent[0]["raw"])


class TestErrorMapping(unittest.TestCase):
    def _client(self, status_code: int, body: dict | None = None) -> GmailClient:
        def handler(_request):
            return httpx.Response(status_code, json=body or {"error": {"message": "x"}})

        return GmailClient("token", transport=httpx.MockTransport(handler))

    def test_401_is_a_revoked_grant_not_a_retry(self):
        with self.assertRaises(GmailAuthRevoked):
            asyncio.run(self._client(401).get_thread("t"))

    def test_403_rate_limit_is_retryable(self):
        client = self._client(403, {"error": {"message": "rateLimitExceeded"}})
        with self.assertRaises(GmailRateLimited):
            asyncio.run(client.get_thread("t"))

    def test_403_missing_scope_is_not_retryable(self):
        # Opposite response to the rate-limit case, same status code.
        client = self._client(403, {"error": {"message": "Insufficient Permission"}})
        with self.assertRaises(GmailAuthRevoked):
            asyncio.run(client.get_thread("t"))

    def test_429_is_retryable(self):
        with self.assertRaises(GmailRateLimited):
            asyncio.run(self._client(429).get_thread("t"))

    def test_history_404_is_distinguishable(self):
        # An aged-out history id is recoverable; a generic error is not.
        with self.assertRaises(GmailNotFound):
            asyncio.run(self._client(404).history_since(1))

    def test_500_is_a_plain_error(self):
        with self.assertRaises(GmailError):
            asyncio.run(self._client(500).get_thread("t"))


class TestTokenExchange(unittest.TestCase):
    def test_success_returns_a_token_with_an_expiry(self):
        def handler(_request):
            return httpx.Response(200, json={"access_token": "at", "expires_in": 3600})

        token = asyncio.run(
            exchange_refresh_token("rt", "id", "secret", transport=httpx.MockTransport(handler))
        )
        self.assertEqual(token.token, "at")
        self.assertFalse(token.expired)

    def test_invalid_grant_is_revocation_and_says_what_to_do(self):
        def handler(_request):
            return httpx.Response(400, json={"error": "invalid_grant"})

        with self.assertRaises(GmailAuthRevoked) as ctx:
            asyncio.run(
                exchange_refresh_token("rt", "id", "s", transport=httpx.MockTransport(handler))
            )
        self.assertIn("Sign in again", str(ctx.exception))

    def test_expiry_has_slack_so_a_token_does_not_die_mid_request(self):
        def handler(_request):
            return httpx.Response(200, json={"access_token": "at", "expires_in": 30})

        token = asyncio.run(
            exchange_refresh_token("rt", "id", "s", transport=httpx.MockTransport(handler))
        )
        self.assertTrue(token.expired)


# ------------------------------------------------------------------- replies


class FakeSession:
    """Just enough session for process_thread. Records what it was told."""

    def __init__(self) -> None:
        self.added: list = []
        self.schedule_rows: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def scalar(self, *_args, **_kwargs):
        return None

    async def scalars(self, *_args, **_kwargs):
        return list(self.schedule_rows)

    async def execute(self, *_args, **_kwargs):
        return None

    def events(self) -> list[str]:
        return [getattr(obj, "type", "") for obj in self.added]


def make_target(thread_id="thread-1"):
    return SimpleNamespace(
        id="t1", email="alex@example.com", gmail_thread_id=thread_id,
        status="active", status_detail="", thread_checked_at=None,
    )


USER = SimpleNamespace(id="u1", email="me@send.test")


class TestReplyDetection(unittest.TestCase):
    def _run(self, gmail: FakeGmail, target, session=None):
        session = session or FakeSession()
        outcome = asyncio.run(
            process_thread(session, user=USER, target=target, gmail=gmail.client())
        )
        return outcome, session

    def test_silent_thread_produces_nothing(self):
        gmail = FakeGmail()
        gmail.threads["thread-1"] = {
            "id": "thread-1",
            "messages": [
                {"id": "m1", "payload": {"headers": [{"name": "From", "value": "Dana <me@send.test>"}]}}
            ],
        }
        outcome, _ = self._run(gmail, make_target())
        self.assertIsNone(outcome)

    def test_genuine_reply_stops_the_sequence(self):
        gmail = FakeGmail()
        gmail.add_inbound(
            "thread-1",
            headers={"From": "Alex <alex@example.com>", "Subject": "Re: inference cost"},
            body="Yes, let's talk Tuesday.",
        )
        target = make_target()
        outcome, _ = self._run(gmail, target)
        self.assertEqual(outcome.verdict, "reply")
        self.assertTrue(outcome.stopped)
        self.assertEqual(target.status, "replied")

    def test_out_of_office_defers_and_does_not_stop(self):
        """The behaviour most worth protecting, end to end."""
        gmail = FakeGmail()
        gmail.add_inbound(
            "thread-1",
            headers={
                "From": "Alex <alex@example.com>",
                "Subject": "Automatic reply: out of office",
                "Auto-Submitted": "auto-replied",
            },
            body="I am away until the 20th.",
        )
        target = make_target()
        due = datetime.now(timezone.utc) + timedelta(days=1)
        session = FakeSession()
        session.schedule_rows = [SimpleNamespace(due_at=due, state="pending")]

        outcome, session = self._run(gmail, target, session)

        self.assertEqual(outcome.verdict, "autoreply")
        self.assertFalse(outcome.stopped)
        self.assertEqual(target.status, "active")          # still running
        self.assertIn("auto_reply", session.events())
        # The next touch was pushed out rather than cancelled.
        self.assertGreater(session.schedule_rows[0].due_at, due)
        self.assertEqual(session.schedule_rows[0].state, "pending")

    def test_bounce_stops_and_suppresses(self):
        gmail = FakeGmail()
        gmail.add_inbound(
            "thread-1",
            headers={
                "From": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>",
                "Subject": "Delivery Status Notification (Failure)",
            },
            body="Your message to alex@example.com was not delivered.",
        )
        target = make_target()
        outcome, session = self._run(gmail, target)
        self.assertEqual(outcome.verdict, "bounce")
        self.assertEqual(target.status, "bounced")
        self.assertTrue(any(type(obj).__name__ == "Suppression" for obj in session.added))

    def test_opt_out_stops_and_suppresses(self):
        gmail = FakeGmail()
        gmail.add_inbound(
            "thread-1",
            headers={"From": "Alex <alex@example.com>", "Subject": "Re: hi"},
            body="Please remove me from your list.",
        )
        target = make_target()
        outcome, _ = self._run(gmail, target)
        self.assertEqual(outcome.verdict, "opt_out")
        self.assertEqual(target.status, "opted_out")

    def test_a_real_reply_after_an_auto_reply_wins(self):
        # Only the latest inbound message decides, so someone who was on leave
        # and then answered is treated as having answered.
        gmail = FakeGmail()
        gmail.add_inbound(
            "thread-1",
            headers={"From": "Alex <alex@example.com>", "Subject": "Out of office"},
            body="Away until Monday.",
        )
        gmail.add_inbound(
            "thread-1",
            headers={"From": "Alex <alex@example.com>", "Subject": "Re: hi"},
            body="Back now - happy to chat.",
        )
        target = make_target()
        outcome, _ = self._run(gmail, target)
        self.assertEqual(outcome.verdict, "reply")
        self.assertEqual(target.status, "replied")

    def test_our_own_messages_are_never_inbound(self):
        gmail = FakeGmail()
        gmail.add_inbound(
            "thread-1",
            headers={"From": "Dana Sharma <me@send.test>", "Subject": "Hi Alex"},
            body="unsubscribe me",  # would be an opt-out if it were inbound
        )
        outcome, _ = self._run(gmail, make_target())
        self.assertIsNone(outcome)

    def test_a_deleted_thread_is_not_an_error(self):
        gmail = FakeGmail()
        target = make_target("gone")
        outcome, _ = self._run(gmail, target)
        self.assertIsNone(outcome)
        self.assertIsNotNone(target.thread_checked_at)

    def test_target_with_no_thread_is_skipped(self):
        outcome, _ = self._run(FakeGmail(), make_target(None))
        self.assertIsNone(outcome)


class TestPayloadParsing(unittest.TestCase):
    def test_plain_text_is_preferred(self):
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": b64("<p>html version</p>")}},
                {"mimeType": "text/plain", "body": {"data": b64("plain version")}},
            ],
        }
        self.assertEqual(plain_text(payload).strip(), "plain version")

    def test_html_only_replies_are_still_readable(self):
        payload = {
            "mimeType": "text/html",
            "body": {"data": b64("<p>Please <b>remove me</b> from your list.</p>")},
        }
        self.assertIn("remove me", plain_text(payload))

    def test_nested_parts_are_walked(self):
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [{"mimeType": "text/plain", "body": {"data": b64("buried text")}}],
                }
            ],
        }
        self.assertIn("buried text", plain_text(payload))

    def test_malformed_base64_does_not_raise(self):
        payload = {"mimeType": "text/plain", "body": {"data": "!!!not base64!!!"}}
        self.assertEqual(plain_text(payload), "")

    def test_headers_are_flattened(self):
        headers = headers_of({"headers": [{"name": "Subject", "value": "Hi"}]})
        self.assertEqual(headers["Subject"], "Hi")


class TestDeliveryStatusExtraction(unittest.TestCase):
    """The bridge between a Gmail payload and hard/soft bounce classification.

    `plain_text` skips `message/delivery-status` by design, so without this
    extractor the `Status:` line never reaches `classify` and every bounce
    looks permanent.
    """

    def dsn_payload(self) -> dict:
        return {
            "mimeType": "multipart/report",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": b64("Delivery failed.")}},
                {
                    "mimeType": "message/delivery-status",
                    "body": {"data": b64("Final-Recipient: rfc822; a@b.com\nStatus: 5.1.1\n")},
                },
            ],
        }

    def test_the_delivery_status_part_is_extracted(self):
        self.assertIn("Status: 5.1.1", delivery_status(self.dsn_payload()))

    def test_the_prose_body_is_left_to_plain_text(self):
        """The two extractors read disjoint parts, so a quoted 'Status:' line
        in the prose cannot be mistaken for the machine report."""
        self.assertNotIn("Delivery failed", delivery_status(self.dsn_payload()))
        self.assertNotIn("Status: 5.1.1", plain_text(self.dsn_payload()))

    def test_an_ordinary_reply_has_no_delivery_status(self):
        payload = {"mimeType": "text/plain", "body": {"data": b64("Sure, Tuesday works.")}}
        self.assertEqual(delivery_status(payload), "")

    def test_nested_report_parts_are_walked(self):
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/report",
                    "parts": [
                        {
                            "mimeType": "message/delivery-status",
                            "body": {"data": b64("Status: 4.2.2\n")},
                        }
                    ],
                }
            ],
        }
        self.assertIn("Status: 4.2.2", delivery_status(payload))


if __name__ == "__main__":
    unittest.main(verbosity=2)
