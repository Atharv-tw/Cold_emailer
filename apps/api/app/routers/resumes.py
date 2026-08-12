"""Resume upload and parsing.

What happens to the file is told to the user at the moment they upload, not in
a policy: it goes to Gemini to be read, what comes back is stored, and the
original is deleted after parsing. This module is where that promise is
actually kept, so the deletion happens in the same request rather than in a
cleanup job that might not run.

The `keep_original` form field still exists below for API backward
compatibility - old clients or direct API calls can still ask to keep the
file - but the profile UI no longer offers that choice, so every upload from
the app itself deletes the original.

Parsing never writes to the profile. Everything extracted comes back as a
suggestion for the user to confirm, because it is a model's guess about
someone's own life and they are the authority on it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select

from ..deps import CurrentUser, Db, GeminiKey, SettingsDep
from ..models import Resume
from ..schemas import ExperienceIn, ParsedResumeOut, ProjectIn, ResumeOut
from ..services.gemini import AIError, GeminiClient
from ..services.resume import ResumeError, extract_text
from ..services.storage import LocalStorage, StorageError

router = APIRouter(prefix="/v1/resumes", tags=["resumes"])

# What the upload screen has to say before the button does anything. Served
# from the API so the wording cannot drift from what the code actually does.
DISCLOSURE = {
    "sent_to_model": "The text of your resume is sent to Google Gemini to be read.",
    "stored": "What it extracts - your headline, bio, links, education, projects and roles - is stored on your profile.",
    "original": "The file itself is deleted as soon as it has been read.",
    "encryption": "Everything is encrypted at rest.",
    "deletion": "'Delete my resume and parsed data' in settings deletes all of it, files included.",
    "no_ocr": "Scanned or image-only PDFs cannot be read. If yours is one, fill the form in by hand instead.",
}


@router.get("/disclosure")
async def disclosure() -> dict[str, str]:
    return DISCLOSURE


@router.post("", response_model=ParsedResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    user: CurrentUser,
    session: Db,
    settings: SettingsDep,
    gemini_key: GeminiKey,
    file: UploadFile = File(...),
    keep_original: bool = Form(False),
) -> ParsedResumeOut:
    data = await file.read()

    try:
        extracted = extract_text(data, file.filename or "resume")
    except ResumeError as exc:
        # Nothing has been written at this point, which is what the message
        # promises the user.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    storage = LocalStorage(settings.storage_dir)
    key = storage.key_for(user.id, file.filename or "resume")
    try:
        storage.put(key, data)
    except StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "could not store the file") from exc

    client = GeminiClient(
        api_key=gemini_key,
        model=settings.gemini_model,
        endpoint=settings.gemini_endpoint,
    )
    try:
        parsed = await client.parse_resume(extracted.text)
    except AIError as exc:
        # A failed parse must not leave the file sitting in storage: the user
        # was told it would be deleted after reading, and it was not kept.
        storage.delete(key)
        print(f"GEMINI_UPLOAD_ERROR: {exc!r}", flush=True)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    row = Resume(
        user_id=user.id,
        filename=file.filename or "resume",
        storage_key=key if keep_original else "",
        parsed=parsed,
        parsed_at=datetime.now(timezone.utc),
        keep_original=keep_original,
    )
    if not keep_original:
        storage.delete(key)
        row.original_deleted_at = datetime.now(timezone.utc)

    session.add(row)
    await session.commit()

    links = parsed.get("links") or {}
    return ParsedResumeOut(
        resume_id=str(row.id),
        filename=row.filename,
        original_kept=keep_original,
        name=str(parsed.get("name", "")),
        headline=str(parsed.get("headline", "")),
        bio=str(parsed.get("bio", "")),
        education=str(parsed.get("education", "")),
        links={k: str(v) for k, v in links.items() if str(v).strip()},
        projects=[ProjectIn(**_project(p)) for p in parsed.get("projects", []) or []],
        experience=[ExperienceIn(**_experience(e)) for e in parsed.get("experience", []) or []],
    )


def _project(raw: dict) -> dict:
    return {
        "name": str(raw.get("name", "")),
        "summary": str(raw.get("summary", "")),
        "tech": str(raw.get("tech", "")),
        "url": str(raw.get("url", "")),
        "demo_url": str(raw.get("demo_url", "")),
        "highlights": [str(h) for h in (raw.get("highlights") or [])],
    }


def _experience(raw: dict) -> dict:
    return {
        "company": str(raw.get("company", "")),
        "role": str(raw.get("role", "")),
        "started": str(raw.get("started", "")),
        "ended": str(raw.get("ended", "")),
        "bullets": [str(b) for b in (raw.get("bullets") or [])],
    }


@router.get("", response_model=list[ResumeOut])
async def list_resumes(user: CurrentUser, session: Db) -> list[ResumeOut]:
    rows = await session.scalars(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    )
    return [
        ResumeOut(
            id=str(row.id),
            filename=row.filename,
            parsed_at=row.parsed_at,
            original_kept=row.keep_original and bool(row.storage_key),
        )
        for row in rows
    ]


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: str, user: CurrentUser, session: Db, settings: SettingsDep
) -> None:
    row = await session.scalar(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such resume")
    if row.storage_key:
        LocalStorage(settings.storage_dir).delete(row.storage_key)
    await session.execute(delete(Resume).where(Resume.id == row.id))
    await session.commit()
