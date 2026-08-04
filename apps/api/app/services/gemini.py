"""Gemini: resume parsing now, email generation in milestone 4.

Ported from the CLI's ai.py. The transport is async httpx rather than urllib,
but the parts worth keeping are unchanged: the API key travels in a header
rather than the query string, because a URL with a secret in it ends up in
proxy logs and shell history; and every failure is mapped to something the
person who pressed the button can act on, rather than a status code.

SYSTEM_RULES carries over verbatim. Left to itself a model writes marketing
copy, which is exactly what gets a personal note deleted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

TIMEOUT_SECONDS = 60

SYSTEM_RULES = """\
You write cold outreach emails for one specific person at a time.

Hard rules:
- Plain text only. No markdown, no bullet points, no bold, no headings.
- At most one URL in the whole email.
- No subject-line gimmicks, no "quick question", no false familiarity.
- No spam-trigger phrasing: act now, limited time, guarantee, 100%, urgent.
- At most one exclamation mark in the entire email, and preferably none.
- Under 900 characters for the body. Shorter replies better.
- Write body paragraphs as single long lines. Do not hard-wrap.
- Never invent facts about the recipient or their company. Use only what you
  are given. If a detail is missing, write around it rather than guessing.
- The ask should be small and easy to say yes or no to.

Return exactly this shape and nothing else:

Subject: <the subject line>

<the body, starting with the greeting>
"""

# The resume parser is told the same thing in a different register: the point
# of structured extraction is to move what is on the page, not to improve it.
EXTRACTION_RULES = """\
You extract structured facts from a resume. You are not writing anything.

Hard rules:
- Use only what the resume says. Never infer, embellish or fill a gap.
- If a field is not in the resume, return an empty string or an empty list.
  An empty field is correct; an invented one is not, and the person reading
  this will not know which is which.
- Copy figures, dates and technology names exactly as written.
- Keep summaries to one sentence, in the resume's own words where possible.
"""

RESUME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "headline": {"type": "string", "description": "One line: what this person does."},
        "bio": {"type": "string", "description": "Two or three sentences, third person."},
        "education": {"type": "string"},
        "links": {
            "type": "object",
            "properties": {
                "portfolio": {"type": "string"},
                "linkedin": {"type": "string"},
                "github": {"type": "string"},
                "other": {"type": "string"},
            },
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "tech": {"type": "string"},
                    "url": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                    "categories": {"type": "array", "items": {"type": "string"}},
                    "best_for": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name"],
            },
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                    "started": {"type": "string"},
                    "ended": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["company"],
            },
        },
    },
    "required": ["name", "headline", "bio", "projects", "experience"],
}


class AIError(Exception):
    """Anything that stops a result coming back, phrased for the user."""


@dataclass(frozen=True)
class GeminiClient:
    api_key: str
    model: str = "gemini-2.5-flash"
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta"
    # Injectable so the error mapping and the parser can be tested against
    # real Gemini response shapes without a network or an API key. Prompt
    # discipline is not something to find out about in production.
    transport: httpx.AsyncBaseTransport | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _url(self) -> str:
        return f"{self.endpoint.rstrip('/')}/models/{self.model}:generateContent"

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise AIError(
                "No Gemini API key is configured, so nothing can be generated. "
                "Set GEMINI_API_KEY - get one at https://aistudio.google.com/apikey"
            )
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS, transport=self.transport
            ) as client:
                response = await client.post(
                    self._url(),
                    json=payload,
                    # In a header, not the query string.
                    headers={"x-goog-api-key": self.api_key},
                )
        except httpx.TimeoutException as exc:
            raise AIError(f"Gemini timed out after {TIMEOUT_SECONDS}s.") from exc
        except httpx.HTTPError as exc:
            raise AIError(f"Could not reach Gemini: {exc}") from exc

        if response.status_code >= 400:
            raise AIError(_error_message(response))
        try:
            return response.json()
        except ValueError as exc:
            raise AIError("Gemini returned a response that was not JSON.") from exc

    async def generate_text(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
    ) -> str:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }
        return _extract_text(await self._post(payload))

    async def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Structured output. Asking for JSON in the prompt is not enough.

        `responseSchema` makes the model's decoder emit conforming JSON rather
        than prose that usually parses, which is the difference between a
        parser that works and one that works until someone's CV has a colon in
        the wrong place.
        """
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        text = _extract_text(await self._post(payload))
        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise AIError("Gemini returned malformed JSON.") from exc
        if not isinstance(parsed, dict):
            raise AIError("Gemini returned JSON that was not an object.")
        return parsed

    async def parse_resume(self, text: str) -> dict[str, Any]:
        """Extract a profile from resume text.

        Returns whatever the model found. The caller shows every field in an
        editable form marked as machine-extracted, because this is a guess
        about someone's own life and they are the authority on it.
        """
        if not text.strip():
            raise AIError("There was no text to read.")

        prompt = (
            f"{EXTRACTION_RULES}\n\n"
            "Extract the fields defined by the schema from the resume below.\n\n"
            "--- resume start ---\n"
            f"{text}\n"
            "--- resume end ---"
        )
        return await self.generate_json(prompt, RESUME_SCHEMA)


def _error_message(response: httpx.Response) -> str:
    try:
        message = response.json()["error"]["message"]
    except Exception:  # noqa: BLE001 - error bodies are not guaranteed JSON
        message = response.text[:300]

    if response.status_code in (401, 403):
        return f"Gemini rejected the API key ({response.status_code}): {message}"
    if response.status_code == 429:
        return "Gemini rate limit or quota exhausted - try again shortly."

    # Google is moving generation to the Interactions API, where structured
    # output is `response_format` and the sampling parameters have been
    # deprecated. `generateContent` is documented as still fully supported,
    # but if a future model rejects a field we send, the raw 400 says
    # "Invalid JSON payload" and nothing about what to do. Name it instead.
    lowered = message.lower()
    if response.status_code == 400 and any(
        field in lowered
        for field in ("generationconfig", "responseschema", "responsemimetype", "temperature")
    ):
        return (
            f"Gemini rejected the request shape ({message}). This usually means "
            f"the model no longer accepts a generationConfig field on "
            f"generateContent. Either pin GEMINI_MODEL to a model that does, or "
            f"port this client to the Interactions API, where structured output "
            f"is `response_format` rather than responseSchema."
        )

    return f"Gemini returned {response.status_code}: {message}"


def _extract_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        blocked = (response.get("promptFeedback") or {}).get("blockReason")
        if blocked:
            raise AIError(f"Gemini refused to answer (reason: {blocked}).")
        raise AIError("Gemini returned no candidates.")

    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    
    reason = candidate.get("finishReason") or "unknown"
    if reason == "MAX_TOKENS":
        raise AIError(
            "Gemini hit its output limit before finishing. If this was a "
            "long resume, try trimming it."
        )

    if not text:
        raise AIError(f"Gemini returned nothing (finishReason: {reason}).")
        
    return text
