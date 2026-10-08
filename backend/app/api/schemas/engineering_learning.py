"""Engineering learning API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.engineering_learning import (
    LearningApprovalStatus,
    LearningRecord,
    LearningRetrieval,
    LearningScope,
    provenance_view,
)


class LearningCreateRequest(BaseModel):
    learning_scope: LearningScope
    agent_id: str | None = None
    task_id: UUID | None = None
    source_snapshot_id: UUID | None = None
    source_element_ids: list[str] = Field(default_factory=list)
    source_element_type: str | None = None
    input_context: dict[str, Any] = Field(default_factory=dict)
    agent_output: dict[str, Any] = Field(default_factory=dict)
    human_correction: dict[str, Any] | None = None
    engineering_reason: str | None = None
    validation_result: str = "NOT_CHECKED"
    applicability: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    engineering_result_id: str | None = None


class LearningCorrectionRequest(BaseModel):
    original_output: dict[str, Any]
    corrected_result: dict[str, Any]
    reason: str | None = None
    learning_scope: LearningScope = LearningScope.PROJECT
    agent_id: str | None = None
    task_id: UUID | None = None
    source_snapshot_id: UUID | None = None
    source_element_ids: list[str] = Field(default_factory=list)
    source_element_type: str | None = None
    applicability: dict[str, Any] = Field(default_factory=dict)
    validation_result: str = "NOT_CHECKED"
    engineering_result_id: str | None = None
    input_context: dict[str, Any] = Field(default_factory=dict)


class LearningDecisionRequest(BaseModel):
    note: str | None = None
    reason: str | None = None


class LearningRecordResponse(BaseModel):
    id: UUID
    project_id: UUID | None = None
    owner_account_id: str
    agent_id: str | None = None
    task_id: UUID | None = None
    source_snapshot_id: UUID | None = None
    source_element_ids: list[str] = Field(default_factory=list)
    source_element_type: str | None = None
    input_context: dict[str, Any] = Field(default_factory=dict)
    agent_output: dict[str, Any] = Field(default_factory=dict)
    human_correction: dict[str, Any] | None = None
    engineering_reason: str | None = None
    validation_result: str
    approval_status: LearningApprovalStatus
    learning_scope: LearningScope
    applicability: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: LearningRecord) -> LearningRecordResponse:
        payload = record.model_dump()
        payload["provenance"] = provenance_view(record)
        return cls.model_validate(payload)


class LearningListResponse(BaseModel):
    records: list[LearningRecordResponse]


class LearningRetrievalResponse(BaseModel):
    project_id: UUID
    account_id: str
    records: list[LearningRecordResponse]
    explanation: str
    authority: str
    overrides_pem: bool
    overrides_rules: bool
    overrides_qa: bool

    @classmethod
    def from_domain(cls, retrieval: LearningRetrieval) -> LearningRetrievalResponse:
        return cls(
            project_id=retrieval.project_id,
            account_id=retrieval.account_id,
            records=[LearningRecordResponse.from_domain(record) for record in retrieval.records],
            explanation=retrieval.explanation,
            authority=retrieval.authority,
            overrides_pem=retrieval.overrides_pem,
            overrides_rules=retrieval.overrides_rules,
            overrides_qa=retrieval.overrides_qa,
        )


class LearningUseResponse(BaseModel):
    learning_record_id: str
    explanation: str
    created_at: datetime


class LearningUseListResponse(BaseModel):
    task_id: UUID
    uses: list[LearningUseResponse]
