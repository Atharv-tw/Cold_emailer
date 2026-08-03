"""Address verification.

The decision table is the whole point, so it is tested exhaustively against
real QuickEmailVerification response shapes. Two rules matter more than the
rest, and both are about not inventing facts:

- Our own failures - timeout, no credits, rate limit, bad key - are `unknown`,
  never `undeliverable`. A vendor outage is not evidence about somebody's
  address, and blocking a send on it would be us making something up.
- A catch-all domain is `risky`, not `deliverable`. "Valid" there means the
  server did not say no, which is not the same as the mailbox existing.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core"))

from app.services.verification import (  # noqa: E402
    DELIVERABLE, RISKY, UNDELIVERABLE, UNKNOWN, EmailVerifier, normalise,
    syntax_ok,
)


def verifier_returning(payload: dict, status_code: int = 200) -> EmailVerifier:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return EmailVerifier(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        # DNS is exercised separately; these tests are about the decision table.
        check_mx=False,
    )


def valid(**overrides) -> dict:
    payload = {
        "result": "valid",
        "reason": "accepted_email",
        "disposable": "false",
        "accept_all": "false",
        "role": "false",
        "free": "false",
        "safe_to_send": "true",
        "did_you_mean": "",
        "success": "true",
    }
    payload.update(overrides)
    return payload


def check(verifier: EmailVerifier, email: str = "dana@example.com"):
    return asyncio.run(verifier.verify(email))


class TestCheapChecks(unittest.TestCase):
    def test_normalise_trims_and_lowercases(self):
        self.assertEqual(normalise("  Dana@Example.COM "), "dana@example.com")

    def test_obvious_typos_never_reach_the_network(self):
        def explode(_request):
            raise AssertionError("a syntax failure must not cost an API call")

        verifier = EmailVerifier(api_key="k", transport=httpx.MockTransport(explode))
        result = check(verifier, "dana@gmail")
        self.assertEqual(result.status, UNDELIVERABLE)
        self.assertEqual(result.source, "syntax")
        self.assertIn("typo", result.detail)

    def test_syntax_accepts_ordinary_addresses(self):
        for address in ("dana@example.com", "dana.s+tag@sub.example.co.uk"):
            self.assertTrue(syntax_ok(address), address)

    def test_syntax_rejects_the_usual_mistakes(self):
        for address in ("dana", "dana@", "@example.com", "dana at example.com", "dana@example"):
            self.assertFalse(syntax_ok(address), address)

    def test_domain_with_no_mx_is_undeliverable_without_an_api_call(self):
        async def scenario():
            def explode(_request):
                raise AssertionError("a missing MX must not cost an API call")

            verifier = EmailVerifier(
                api_key="k", transport=httpx.MockTransport(explode), check_mx=True
            )
            import app.services.verification as module

            original = module.has_mx
            module.has_mx = lambda domain: _resolved(False)
            try:
                return await verifier.verify("dana@nosuchdomain.invalid")
            finally:
                module.has_mx = original

        result = asyncio.run(scenario())
        self.assertEqual(result.status, UNDELIVERABLE)
        self.assertEqual(result.reason, "no_mx_record")

    def test_dns_failure_does_not_block_the_address(self):
        async def scenario():
            verifier = EmailVerifier(
                api_key="k",
                transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=valid())),
                check_mx=True,
            )
            import app.services.verification as module

            original = module.has_mx
            # None means "DNS could not answer", which is not the same as
            # "this domain has no mail exchanger".
            module.has_mx = lambda domain: _resolved(None)
            try:
                return await verifier.verify("dana@example.com")
            finally:
                module.has_mx = original

        self.assertEqual(asyncio.run(scenario()).status, DELIVERABLE)


async def _resolved(value):
    return value


class TestDecisionTable(unittest.TestCase):
    def test_clean_valid_address_is_deliverable(self):
        result = check(verifier_returning(valid()))
        self.assertEqual(result.status, DELIVERABLE)
        self.assertEqual(result.source, "quickemailverification")

    def test_invalid_is_undeliverable(self):
        result = check(verifier_returning(valid(result="invalid", reason="rejected_email")))
        self.assertEqual(result.status, UNDELIVERABLE)
        self.assertTrue(result.blocks_sending)

    def test_typo_suggestion_is_passed_through(self):
        result = check(
            verifier_returning(
                valid(result="invalid", did_you_mean="dana@gmail.com", reason="rejected_email")
            )
        )
        self.assertEqual(result.did_you_mean, "dana@gmail.com")
        self.assertIn("dana@gmail.com", result.detail)

    def test_catch_all_domain_is_risky_not_deliverable(self):
        result = check(verifier_returning(valid(accept_all="true")))
        self.assertEqual(result.status, RISKY)
        self.assertEqual(result.reason, "accept_all")
        self.assertFalse(result.blocks_sending)  # a warning, not a block
        self.assertIn("could not be confirmed", result.detail)

    def test_disposable_address_is_risky(self):
        result = check(verifier_returning(valid(disposable="true")))
        self.assertEqual(result.status, RISKY)
        self.assertEqual(result.reason, "disposable")

    def test_role_address_is_risky_and_says_why(self):
        result = check(verifier_returning(valid(role="true")))
        self.assertEqual(result.status, RISKY)
        self.assertIn("info@", result.detail)

    def test_unsafe_to_send_is_risky_even_when_nothing_else_flags(self):
        result = check(verifier_returning(valid(safe_to_send="false")))
        self.assertEqual(result.status, RISKY)

    def test_free_provider_alone_is_not_risky(self):
        # Almost every individual has a Gmail address. Flagging that would
        # mark most real people as risky.
        self.assertEqual(check(verifier_returning(valid(free="true"))).status, DELIVERABLE)

    def test_vendor_unknown_stays_unknown(self):
        result = check(verifier_returning(valid(result="unknown", reason="timeout")))
        self.assertEqual(result.status, UNKNOWN)
        self.assertFalse(result.blocks_sending)
        self.assertIn("still send", result.detail)

    def test_real_booleans_are_handled_as_well_as_strings(self):
        result = check(verifier_returning(valid(accept_all=True, success=True)))
        self.assertEqual(result.status, RISKY)

    def test_unrecognised_result_is_unknown_not_deliverable(self):
        result = check(verifier_returning(valid(result="something_new")))
        self.assertEqual(result.status, UNKNOWN)


class TestOurFailuresNeverBlock(unittest.TestCase):
    """A vendor problem is not evidence about somebody's address."""

    def test_no_api_key_configured(self):
        result = asyncio.run(EmailVerifier(check_mx=False).verify("dana@example.com"))
        self.assertEqual(result.status, UNKNOWN)
        self.assertEqual(result.reason, "verification_not_configured")

    def test_out_of_credits(self):
        result = check(verifier_returning({}, status_code=402))
        self.assertEqual(result.status, UNKNOWN)
        self.assertEqual(result.reason, "verifier_out_of_credits")

    def test_rate_limited(self):
        result = check(verifier_returning({}, status_code=429))
        self.assertEqual(result.status, UNKNOWN)
        self.assertEqual(result.reason, "verifier_rate_limited")

    def test_bad_key(self):
        result = check(verifier_returning({}, status_code=401))
        self.assertEqual(result.status, UNKNOWN)
        self.assertEqual(result.reason, "verifier_unauthorised")

    def test_server_error(self):
        result = check(verifier_returning({}, status_code=500))
        self.assertEqual(result.status, UNKNOWN)

    def test_timeout(self):
        def handler(_request):
            raise httpx.ReadTimeout("too slow")

        verifier = EmailVerifier(
            api_key="k", transport=httpx.MockTransport(handler), check_mx=False
        )
        result = check(verifier)
        self.assertEqual(result.status, UNKNOWN)
        self.assertEqual(result.reason, "verifier_timeout")

    def test_unreachable(self):
        def handler(_request):
            raise httpx.ConnectError("no route")

        verifier = EmailVerifier(
            api_key="k", transport=httpx.MockTransport(handler), check_mx=False
        )
        self.assertEqual(check(verifier).reason, "verifier_unreachable")

    def test_malformed_body(self):
        def handler(_request):
            return httpx.Response(200, content=b"<html>not json</html>")

        verifier = EmailVerifier(
            api_key="k", transport=httpx.MockTransport(handler), check_mx=False
        )
        self.assertEqual(check(verifier).status, UNKNOWN)

    def test_success_false_is_unknown(self):
        result = check(verifier_returning({"success": "false", "message": "insufficient credit"}))
        self.assertEqual(result.status, UNKNOWN)
        self.assertIn("insufficient credit", result.detail)

    def test_no_failure_mode_ever_reports_undeliverable(self):
        # The property, stated once: nothing that goes wrong on our side is
        # allowed to become a claim that someone's address does not exist.
        for code in (401, 402, 403, 429, 500, 503):
            self.assertNotEqual(check(verifier_returning({}, status_code=code)).status, UNDELIVERABLE)


class TestRequestShape(unittest.TestCase):
    def test_request_matches_the_documented_api(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json=valid())

        verifier = EmailVerifier(
            api_key="secret-key", transport=httpx.MockTransport(handler), check_mx=False
        )
        check(verifier, "Dana@Example.com")

        self.assertEqual(captured["method"], "GET")
        self.assertEqual(captured["path"], "/v1/verify")
        self.assertEqual(captured["params"]["apikey"], "secret-key")
        # Normalised before it leaves, so the cache key and the vendor agree.
        self.assertEqual(captured["params"]["email"], "dana@example.com")

    def test_sandbox_endpoint_is_usable(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return httpx.Response(200, json=valid())

        verifier = EmailVerifier(
            api_key="k",
            endpoint="https://api.quickemailverification.com/v1/verify/sandbox",
            transport=httpx.MockTransport(handler),
            check_mx=False,
        )
        check(verifier)
        self.assertTrue(captured["path"].endswith("/sandbox"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
