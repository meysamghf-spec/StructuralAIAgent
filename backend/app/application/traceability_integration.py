"""Traceability integration helpers and extension points."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.domain.models.traceability import (
    TraceObjectType,
    TraceabilityRelationshipType,
)

if TYPE_CHECKING:
    from app.application.traceability_service import TraceabilityService


ANALYSIS_TRACE_EXTENSION = "analysis"
DESIGN_TRACE_EXTENSION = "design"
REPORT_TRACE_EXTENSION = "report"


def record_source_to_memory(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    file_id: UUID,
    memory_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.FILE.value,
        source_id=file_id,
        target_type=TraceObjectType.MEMORY.value,
        target_id=memory_id,
        relationship_type=TraceabilityRelationshipType.SOURCE_TO_MEMORY,
        metadata=metadata,
    )


def record_decision_to_approval(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    memory_id: UUID,
    approval_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.MEMORY.value,
        source_id=memory_id,
        target_type=TraceObjectType.APPROVAL.value,
        target_id=approval_id,
        relationship_type=TraceabilityRelationshipType.DECISION_TO_APPROVAL,
        metadata=metadata,
    )


def record_approval_to_model(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    approval_id: UUID,
    model_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.APPROVAL.value,
        source_id=approval_id,
        target_type=TraceObjectType.PEM_SNAPSHOT.value,
        target_id=model_id,
        metadata=metadata,
    )


def record_model_to_analysis(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    model_id: UUID,
    analysis_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.PEM_SNAPSHOT.value,
        source_id=model_id,
        target_type=TraceObjectType.ANALYSIS_RESULT.value,
        target_id=analysis_id,
        relationship_type=TraceabilityRelationshipType.MODEL_TO_ANALYSIS,
        metadata=metadata,
    )


def record_analysis_to_design(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    analysis_id: UUID,
    design_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.ANALYSIS_RESULT.value,
        source_id=analysis_id,
        target_type=TraceObjectType.DESIGN_RESULT.value,
        target_id=design_id,
        relationship_type=TraceabilityRelationshipType.ANALYSIS_TO_DESIGN,
        metadata=metadata,
    )


def record_design_to_report(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    design_id: UUID,
    report_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.DESIGN_RESULT.value,
        source_id=design_id,
        target_type=TraceObjectType.REPORT.value,
        target_id=report_id,
        relationship_type=TraceabilityRelationshipType.DESIGN_TO_REPORT,
        metadata=metadata,
    )


def record_request_to_agent_execution(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    request_id: UUID,
    execution_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.USER_REQUEST.value,
        source_id=request_id,
        target_type=TraceObjectType.AGENT_EXECUTION.value,
        target_id=execution_id,
        relationship_type=TraceabilityRelationshipType.REQUEST_TO_AGENT_EXECUTION,
        metadata=metadata,
    )


def record_agent_execution_to_result(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    execution_id: UUID,
    result_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.AGENT_EXECUTION.value,
        source_id=execution_id,
        target_type=TraceObjectType.AGENT_RESULT.value,
        target_id=result_id,
        relationship_type=TraceabilityRelationshipType.AGENT_EXECUTION_TO_RESULT,
        metadata=metadata,
    )


def record_agent_result_to_validation(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    result_id: UUID,
    validation_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.AGENT_RESULT.value,
        source_id=result_id,
        target_type=TraceObjectType.ANALYSIS_RESULT.value,
        target_id=validation_id,
        relationship_type=TraceabilityRelationshipType.AGENT_RESULT_TO_VALIDATION,
        metadata=metadata,
    )


def record_agent_result_to_approval(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    result_id: UUID,
    approval_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.AGENT_RESULT.value,
        source_id=result_id,
        target_type=TraceObjectType.APPROVAL.value,
        target_id=approval_id,
        relationship_type=TraceabilityRelationshipType.AGENT_RESULT_TO_APPROVAL,
        metadata=metadata,
    )


def record_approval_to_agent_result(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    approval_id: UUID,
    result_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.APPROVAL.value,
        source_id=approval_id,
        target_type=TraceObjectType.AGENT_RESULT.value,
        target_id=result_id,
        relationship_type=TraceabilityRelationshipType.APPROVAL_TO_AGENT_RESULT,
        metadata=metadata,
    )


def record_agent_result_to_report(
    traceability: TraceabilityService,
    *,
    project_id: UUID,
    result_id: UUID,
    report_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    traceability.create_link(
        project_id,
        source_type=TraceObjectType.AGENT_RESULT.value,
        source_id=result_id,
        target_type=TraceObjectType.REPORT.value,
        target_id=report_id,
        relationship_type=TraceabilityRelationshipType.AGENT_RESULT_TO_REPORT,
        metadata=metadata,
    )
