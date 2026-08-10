"""Bulk import: a spreadsheet of leads becomes reviewed, guarded targets.

Two steps, and the file is uploaded to both. That is on purpose: the commit
re-reads and re-validates the source rather than trusting rows the browser
sends back, so nothing the client edits in between can slip a suppressed or
duplicate address past the gates.

* ``preview`` reads the file, guesses which column feeds which field, and
  returns a verdict per row - duplicates, suppressed contacts, invalid or
  missing emails, and the rows still needing a hook - without writing anything.
* ``commit`` re-reads it and adds only the importable rows, each one first put
  through the same suppression, duplicate and cross-user-guard checks a single
  add makes. Deliverability is deferred: an imported target is verified in the
  send path the first time a message is about to go out, not once per row here.

Import deliberately does *not* require a complete profile the way single-add
does. Building a lead list is data entry and can happen before the profile is
ready to write from; the completeness gate still applies when a draft is
generated and when anything is sent.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from ..deps import CurrentUser, Db, SettingsDep
from ..models import DeadAddress, Event, Suppression, Target
from ..schemas import (
    ImportCommitOut,
    ImportField,
    ImportPreviewOut,
    ImportRowOut,
    ImportSummary,
)
from ..services import guard, leads_import
from ..services.sheets import SheetError, read_table, suggest_mapping
from ..services.verification import normalise

router = APIRouter(prefix="/v1/import", tags=["import"])

# A lead list is text; anything larger than this is not one, and reading it
# would only tie up the request. Well above a realistic 5000-row export.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _fields_out() -> list[ImportField]:
    return [
        ImportField(key=f.key, label=f.label, required=f.required)
        for f in leads_import.FIELDS
    ]


def _parse_mapping(raw: str) -> dict[str, str]:
    """A header->field-key map from the form, keeping only known field keys."""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "mapping is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "mapping must be an object")
    return {
        str(header): str(field_key)
        for header, field_key in parsed.items()
        if str(field_key) in leads_import.FIELD_KEYS
    }


async def _read(file: UploadFile) -> tuple[list[str], list[dict[str, str]]]:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "That file is larger than 10 MB - a lead list should be well under that.",
        )
    try:
        return read_table(data, file.filename or "upload")
    except SheetError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


async def _known_emails(session, user_id) -> tuple[set[str], set[str], set[str]]:
    """Existing target addresses, suppressed addresses, and dead ones.

    The third set is not user-scoped: `dead_addresses` records mailboxes that
    hard-bounced for anybody here, and there is no sense letting one user
    import an address another user has already proved does not exist.
    """
    existing = {
        normalise(email)
        for email in await session.scalars(
            select(Target.email).where(Target.user_id == user_id)
        )
    }
    suppressed = {
        normalise(email)
        for email in await session.scalars(
            select(Suppression.email).where(Suppression.user_id == user_id)
        )
    }
    dead = {
        normalise(email)
        for email in await session.scalars(select(DeadAddress.email))
    }
    return existing, suppressed, dead


def _row_out(row: leads_import.ReviewRow) -> ImportRowOut:
    return ImportRowOut(
        index=row.index,
        name=row.values.get("name", ""),
        email=row.email,
        company=row.values.get("company", ""),
        role=row.values.get("role", ""),
        status=row.status,
        issues=row.issues,
        importable=row.importable,
    )


@router.get("/fields", response_model=list[ImportField])
async def fields(user: CurrentUser) -> list[ImportField]:
    """The columns a file may map onto - so the UI can offer them before upload."""
    return _fields_out()


@router.post("/preview", response_model=ImportPreviewOut)
async def preview(
    user: CurrentUser,
    session: Db,
    file: UploadFile = File(...),
    mapping: str = Form(""),
) -> ImportPreviewOut:
    headers, rows = await _read(file)
    chosen = _parse_mapping(mapping) or suggest_mapping(headers, leads_import.mappable_fields())

    existing, suppressed, dead = await _known_emails(session, user.id)
    result = leads_import.review(
        rows,
        chosen,
        existing_emails=existing,
        suppressed_emails=suppressed,
        dead_emails=dead,
    )

    return ImportPreviewOut(
        headers=headers,
        fields=_fields_out(),
        mapping=result.mapping,
        unmapped_required=result.unmapped_required,
        rows=[_row_out(row) for row in result.rows],
        summary=ImportSummary(**result.summary()),
    )


@router.post("/commit", response_model=ImportCommitOut)
async def commit(
    user: CurrentUser,
    session: Db,
    settings: SettingsDep,
    file: UploadFile = File(...),
    mapping: str = Form(""),
) -> ImportCommitOut:
    headers, rows = await _read(file)
    chosen = _parse_mapping(mapping) or suggest_mapping(headers, leads_import.mappable_fields())

    existing, suppressed, dead = await _known_emails(session, user.id)
    result = leads_import.review(
        rows,
        chosen,
        existing_emails=existing,
        suppressed_emails=suppressed,
        dead_emails=dead,
    )

    importable = [row for row in result.rows if row.importable]
    # The cross-user guard, checked here as it is for single-add: someone being
    # piled on by many accounts of this platform is not added, even in bulk.
    blocked = await guard.blocked_emails(
        session, [row.email for row in importable], settings.recipient_guard_secret_bytes
    )

    created = 0
    skipped_reasons: dict[str, int] = {}

    def note_skip(reason: str) -> None:
        skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

    for row in result.rows:
        if not row.importable:
            note_skip(row.status)
            continue
        if row.email in blocked:
            note_skip("guard_blocked")
            continue

        values = row.values
        target = Target(
            user_id=user.id,
            name=values.get("name", ""),
            email=row.email,
            company=values.get("company", ""),
            role=values.get("role", ""),
            target_type=values.get("target_type", "founder"),
            company_type=values.get("company_type", "other"),
            intent=values.get("intent", "internship"),
            timezone=values.get("timezone", ""),
            hook=values.get("hook", ""),
            links=leads_import.links_from(values),
            verification=dict(leads_import.IMPORT_PENDING_VERIFICATION),
            status="draft",
        )
        session.add(target)
        await session.flush()
        session.add(
            Event(user_id=user.id, target_id=target.id, type="target_imported", detail="")
        )
        created += 1

    await session.commit()

    skipped = sum(skipped_reasons.values())
    return ImportCommitOut(
        created=created,
        skipped=skipped,
        skipped_reasons=skipped_reasons,
        summary=ImportSummary(**result.summary()),
    )
