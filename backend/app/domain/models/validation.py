"""ValidationEngine domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ValidationCategory(StrEnum):
    INPUT = "INPUT"
    ARCHITECTURE = "ARCHITECTURE"
    STRUCTURAL = "STRUCTURAL"
    ANALYSIS = "ANALYSIS"
    DESIGN = "DESIGN"
    OUTPUT = "OUTPUT"
    CODE = "CODE"


class ValidationStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"


class ValidationFinding(BaseModel):
    category: ValidationCategory
    status: ValidationStatus
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    project_id: UUID
    overall_status: ValidationStatus
    findings: list[ValidationFinding] = Field(default_factory=list)
    summary: str
