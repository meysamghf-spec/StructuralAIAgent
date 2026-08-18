"""Revision API response schemas."""

from __future__ import annotations

from pydantic import BaseModel

from app.api.schemas.common import RevisionResponse


class RevisionListResponse(BaseModel):
    revisions: list[RevisionResponse]
