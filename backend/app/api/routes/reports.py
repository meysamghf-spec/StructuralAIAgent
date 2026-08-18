"""Engineering reporting REST endpoints — /api/v1/reports."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_report_generation_service
from app.api.schemas.reporting import (
    ReportCreateRequest,
    ReportGenerateRequest,
    ReportListResponse,
    ReportResponse,
    ReportTraceabilityResponse,
    ReportVersionResponse,
)
from app.application.report_generation_service import ReportGenerationService
from app.domain.models.reporting import ReportGenerationRequest, ReportType

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    body: ReportCreateRequest,
    report_service: Annotated[ReportGenerationService, Depends(get_report_generation_service)],
) -> ReportResponse:
    report = report_service.create_report(
        body.project_id,
        report_type=body.report_type,
        title=body.title,
        metadata=body.metadata,
        created_by=body.created_by,
    )
    return ReportResponse.from_domain(report)


@router.get("", response_model=ReportListResponse)
def list_reports(
    report_service: Annotated[ReportGenerationService, Depends(get_report_generation_service)],
    project_id: UUID = Query(...),
    report_type: ReportType | None = Query(default=None),
) -> ReportListResponse:
    reports = report_service.list_reports(project_id, report_type=report_type)
    return ReportListResponse(reports=[ReportResponse.from_domain(item) for item in reports])


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: UUID,
    report_service: Annotated[ReportGenerationService, Depends(get_report_generation_service)],
    project_id: UUID = Query(...),
) -> ReportResponse:
    report = report_service.get_report(project_id, report_id)
    return ReportResponse.from_domain(report)


@router.post("/{report_id}/generate", response_model=ReportVersionResponse)
def generate_report_version(
    report_id: UUID,
    body: ReportGenerateRequest,
    report_service: Annotated[ReportGenerationService, Depends(get_report_generation_service)],
    project_id: UUID = Query(...),
) -> ReportVersionResponse:
    version = report_service.generate_version(
        ReportGenerationRequest(
            project_id=project_id,
            report_id=report_id,
            report_type=body.report_type,
            output_format=body.output_format,
            requested_by=body.requested_by,
            parameters=body.parameters,
        )
    )
    return ReportVersionResponse.from_domain(version)


@router.get("/{report_id}/versions/{version}", response_model=ReportVersionResponse)
def get_report_version(
    report_id: UUID,
    version: int,
    report_service: Annotated[ReportGenerationService, Depends(get_report_generation_service)],
    project_id: UUID = Query(...),
) -> ReportVersionResponse:
    report_version = report_service.get_report_version(project_id, report_id, version)
    return ReportVersionResponse.from_domain(report_version)


@router.get("/{report_id}/traceability", response_model=ReportTraceabilityResponse)
def get_report_traceability(
    report_id: UUID,
    report_service: Annotated[ReportGenerationService, Depends(get_report_generation_service)],
    project_id: UUID = Query(...),
) -> ReportTraceabilityResponse:
    payload = report_service.get_report_traceability(project_id, report_id)
    return ReportTraceabilityResponse.model_validate(payload)
