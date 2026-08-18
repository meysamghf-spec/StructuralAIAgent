"""ValidationEngine API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.validation import ValidationReport


class ValidationFindingResponse(BaseModel):
    category: str
    status: str
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReportResponse(BaseModel):
    project_id: UUID
    overall_status: str
    findings: list[ValidationFindingResponse]
    summary: str

    @classmethod
    def from_domain(cls, report: ValidationReport) -> ValidationReportResponse:
        return cls(
            project_id=report.project_id,
            overall_status=report.overall_status.value,
            findings=[
                ValidationFindingResponse(
                    category=finding.category.value,
                    status=finding.status.value,
                    code=finding.code,
                    message=finding.message,
                    details=finding.details,
                )
                for finding in report.findings
            ],
            summary=report.summary,
        )
