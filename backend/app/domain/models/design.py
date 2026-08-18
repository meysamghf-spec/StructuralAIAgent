"""Design engine domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DesignStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"


class DesignRequest(BaseModel):
    project_id: UUID
    design_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class DesignResult(BaseModel):
    project_id: UUID
    design_type: str
    status: DesignStatus
    message: str
    code_edition: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
