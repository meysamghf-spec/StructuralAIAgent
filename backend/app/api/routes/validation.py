"""ValidationEngine REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_validation_engine_service
from app.api.schemas.validation import ValidationReportResponse
from app.application.validation_engine_service import ValidationEngineService

router = APIRouter(prefix="/projects", tags=["validation"])


@router.post("/{project_id}/validate", response_model=ValidationReportResponse)
def validate_project(
    project_id: UUID,
    validation_service: Annotated[ValidationEngineService, Depends(get_validation_engine_service)],
) -> ValidationReportResponse:
    report = validation_service.validate_project(project_id)
    return ValidationReportResponse.from_domain(report)
