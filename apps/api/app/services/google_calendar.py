"""Google Calendar, over HTTP.

The reminder layer, and nothing more. The database schedule decides when a
follow-up is due; this module only mirrors that decision onto the user's
calendar so the reminder shows up in the day they actually look at. Every call
here is best-effort at the layer above: a calendar that is briefly out of sync
is a cosmetic problem, and it must never be allowed to change what gets sent.

No SDK, for the same reason as Gmail: three endpoints - insert, patch, delete -
do everything, and the failures worth handling (a revoked grant, a missing
event) are ours to recognise either way.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx

API_BASE = "https://www.googleapis.com/calendar/v3"
TIMEOUT_SECONDS = 30

# A follow-up is a moment, not a meeting. Fifteen minutes is long enough to be
# visible in a day view without pretending to block the time.
EVENT_LENGTH = timedelta(minutes=15)


class CalendarError(Exception):
    """A calendar call failed for a reason worth retrying later."""


class CalendarAuthRevoked(CalendarError):
    """The user removed calendar access, or never granted it. Stop syncing."""


class CalendarNotFound(CalendarError):
    """The event is already gone. For a delete, that is success."""


def _rfc3339(when: datetime) -> str:
    # Calendar wants an offset; a naive datetime is treated as floating local
    # time, which is exactly the ambiguity the rest of this system avoids.
    return when.isoformat()


def build_event_body(
    *,
    title: str,
    when: datetime,
    description: str,
    url: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": title,
        "description": description,
        "start": {"dateTime": _rfc3339(when)},
        "end": {"dateTime": _rfc3339(when + EVENT_LENGTH)},
        # The user's own default reminders, rather than imposing one: this is a
        # note in their calendar, not an alarm we decided they wanted.
        "reminders": {"useDefault": True},
    }
    if url:
        body["source"] = {"title": "Open in outreach", "url": url}
    return body


@dataclass(frozen=True)
class CalendarClient:
    access_token: str
    calendar_id: str = "primary"
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
            raise CalendarError("Calendar timed out") from exc
        except httpx.HTTPError as exc:
            raise CalendarError(f"could not reach Calendar: {exc}") from exc

        if response.status_code == 401:
            raise CalendarAuthRevoked(_detail(response) or "Google rejected the credentials")
        if response.status_code == 403:
            detail = _detail(response)
            if "rateLimitExceeded" in detail or "userRateLimitExceeded" in detail:
                raise CalendarError(detail)
            # No calendar scope reads as a 403 here; treat it like a revoked
            # grant so the sync stops for this user rather than retrying.
            raise CalendarAuthRevoked(f"Calendar refused the request: {detail}")
        if response.status_code in (404, 410):
            raise CalendarNotFound(_detail(response))
        if response.status_code == 429:
            raise CalendarError(_detail(response))
        if response.status_code >= 400:
            raise CalendarError(f"Calendar returned {response.status_code}: {_detail(response)}")

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise CalendarError("Calendar returned a response that was not JSON") from exc

    async def create_event(self, body: dict[str, Any]) -> str:
        result = await self._request(
            "POST", f"/calendars/{self.calendar_id}/events", json=body
        )
        return str(result.get("id", ""))

    async def update_event(self, event_id: str, body: dict[str, Any]) -> None:
        await self._request(
            "PATCH", f"/calendars/{self.calendar_id}/events/{event_id}", json=body
        )

    async def delete_event(self, event_id: str) -> None:
        """Remove an event. Already-gone is success, not an error."""
        try:
            await self._request(
                "DELETE", f"/calendars/{self.calendar_id}/events/{event_id}"
            )
        except CalendarNotFound:
            return


def _detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300]
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message", ""))
    return str(error or "")[:300]
