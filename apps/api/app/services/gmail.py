"""Gmail, over HTTP.

Two failure modes shape this module, and both are silent by default:

- **A revoked grant.** A user who removes access in their Google account gets
  no callback. The next send simply fails with 401 and `invalid_grant`. If that
  is treated as a transient error the queue retries forever; it has to be
  recognised, recorded, and surfaced to the user as "reconnect your account".
- **An expired watch.** `users.watch` returns an expiry about seven days out
  and then stops delivering push notifications with no error and no callback.
  Nothing tells us. That is why the expiry is stored and re-armed daily.

No SDK. The surface used here is six endpoints, and a dependency that wraps
them would still leave both problems above to solve by hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

import httpx

from outreach_core.mime import to_gmail_raw

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
TIMEOUT_SECONDS = 30


class GmailError(Exception):
    """A send or read failed for a reason worth retrying."""


class GmailAuthRevoked(GmailError):
    """The user removed access. Retrying will never work; stop and tell them."""


class GmailRateLimited(GmailError):
    """Back off - Gmail is asking us to slow down, not refusing outright."""


@dataclass(frozen=True)
class SentMessage:
    gmail_message_id: str
    thread_id: str
    # The Message-ID Gmail actually assigned, read back rather than assumed.
    # Threading the next touch against a value we invented would break the
    # moment Gmail rewrote it, which it does.
    rfc822_message_id: str


@dataclass(frozen=True)
class GmailClient:
    access_token: str
    transport: httpx.AsyncBaseTransport | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            transport=self.transport,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with self._client() as client:
                response = await client.request(method, f"{API_BASE}{path}", **kwargs)
        except httpx.TimeoutException as exc:
            raise GmailError("Gmail timed out") from exc
        except httpx.HTTPError as exc:
            raise GmailError(f"could not reach Gmail: {exc}") from exc

        if response.status_code == 401:
            raise GmailAuthRevoked(_detail(response) or "Google rejected the credentials")
        if response.status_code == 403:
            detail = _detail(response)
            # 403 covers both "you have been throttled" and "you do not have
            # this scope", which need opposite responses.
            if "rateLimitExceeded" in detail or "userRateLimitExceeded" in detail:
                raise GmailRateLimited(detail)
            raise GmailAuthRevoked(f"Google refused the request: {detail}")
        if response.status_code == 429:
            raise GmailRateLimited(_detail(response))
        if response.status_code == 404:
            raise GmailNotFound(_detail(response))
        if response.status_code >= 400:
            raise GmailError(f"Gmail returned {response.status_code}: {_detail(response)}")

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise GmailError("Gmail returned a response that was not JSON") from exc

    # ------------------------------------------------------------------ send

    async def send(self, message: EmailMessage, thread_id: str | None = None) -> SentMessage:
        payload: dict[str, Any] = {"raw": to_gmail_raw(message)}
        if thread_id:
            # Threading needs both this and the In-Reply-To/References headers:
            # threadId keeps it in the right conversation in Gmail's own UI,
            # the headers keep it there in everyone else's client.
            payload["threadId"] = thread_id

        result = await self._request("POST", "/messages/send", json=payload)
        gmail_id = str(result.get("id", ""))
        return SentMessage(
            gmail_message_id=gmail_id,
            thread_id=str(result.get("threadId", "")),
            rfc822_message_id=await self.message_id_header(gmail_id) if gmail_id else "",
        )

    async def message_id_header(self, gmail_message_id: str) -> str:
        result = await self._request(
            "GET",
            f"/messages/{gmail_message_id}",
            params={"format": "metadata", "metadataHeaders": "Message-ID"},
        )
        for header in (result.get("payload") or {}).get("headers") or []:
            if header.get("name", "").lower() == "message-id":
                return str(header.get("value", ""))
        return ""

    # ---------------------------------------------------------------- reading

    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/threads/{thread_id}", params={"format": "metadata"}
        )

    async def get_message(self, message_id: str, *, fmt: str = "full") -> dict[str, Any]:
        return await self._request("GET", f"/messages/{message_id}", params={"format": fmt})

    async def history_since(self, start_history_id: int) -> dict[str, Any]:
        """Changes since a history id.

        A 404 means the stored id has aged out of Gmail's history window. That
        is recoverable - resync the threads directly - but only if the caller
        can tell it apart from a transient failure, hence GmailNotFound.
        """
        return await self._request(
            "GET",
            "/history",
            params={
                "startHistoryId": str(start_history_id),
                "historyTypes": "messageAdded",
                "labelId": "INBOX",
            },
        )

    # ------------------------------------------------------------------ watch

    async def watch(self, topic: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/watch", json={"topicName": topic, "labelIds": ["INBOX"]}
        )

    async def stop_watch(self) -> dict[str, Any]:
        return await self._request("POST", "/stop")


class GmailNotFound(GmailError):
    """The resource is gone - for history, the id is older than the window."""


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", {}).get("message", ""))[:300]
    except Exception:  # noqa: BLE001 - error bodies are not guaranteed JSON
        return response.text[:300]


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_at: datetime

    @property
    def expired(self) -> bool:
        # A minute of slack, so a token does not expire mid-request.
        return datetime.now(timezone.utc) >= self.expires_at - timedelta(minutes=1)


async def exchange_refresh_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AccessToken:
    """Trade a refresh token for an access token.

    `invalid_grant` here is the revocation signal. Google returns it when the
    user removed access, changed their password, or the token simply expired -
    all of which mean the same thing to us: stop sending and ask them to
    reconnect.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
    except httpx.HTTPError as exc:
        raise GmailError(f"could not reach Google's token endpoint: {exc}") from exc

    if response.status_code >= 400:
        body = response.text[:300]
        if "invalid_grant" in body or response.status_code == 400:
            raise GmailAuthRevoked(
                "Google access has been revoked or expired. Sign in again to reconnect."
            )
        raise GmailError(f"token exchange failed ({response.status_code}): {body}")

    payload = response.json()
    token = str(payload.get("access_token", ""))
    if not token:
        raise GmailError("token exchange returned no access token")

    return AccessToken(
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 3600))),
    )
