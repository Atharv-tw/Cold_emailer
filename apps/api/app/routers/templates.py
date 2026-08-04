"""Generation template catalog."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.email_templates import all_templates

router = APIRouter(prefix="/v1/templates", tags=["templates"])


class TemplateOut(BaseModel):
    key: str
    name: str
    description: str


@router.get("", response_model=list[TemplateOut])
async def list_templates() -> list[TemplateOut]:
    return [
        TemplateOut(
            key=template.key,
            name=template.name,
            description=template.description,
        )
        for template in all_templates()
    ]
