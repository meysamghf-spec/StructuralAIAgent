"""Prompt template API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.prompt_template import PromptTemplate, PromptTemplateStatus


class CreatePromptTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    template: str = Field(..., min_length=1)
    variables_schema: dict[str, Any] = Field(default_factory=dict)


class PromptTemplateResponse(BaseModel):
    id: UUID
    agent_version_id: UUID
    version: int
    name: str
    template: str
    variables_schema: dict[str, Any] = Field(default_factory=dict)
    status: PromptTemplateStatus
    created_at: datetime
    created_by: str | None = None

    @classmethod
    def from_domain(cls, prompt: PromptTemplate) -> PromptTemplateResponse:
        return cls.model_validate(prompt.model_dump())


class PromptTemplateListResponse(BaseModel):
    prompts: list[PromptTemplateResponse]
