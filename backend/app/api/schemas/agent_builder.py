"""Agent Builder API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.agent import AgentCapabilityResponse, AgentDefinitionResponse, AgentVersionResponse
from app.application.agent_builder_service import AgentBuilderVersionDetail
from app.domain.models.agent_builder import (
    AgentBuilderPublicationRecord,
    AgentBuilderValidationIssue,
    AgentBuilderValidationResult,
    AgentVersionTestRecord,
)


class CreateBuilderAgentRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    purpose: str | None = None
    engineering_domain: str | None = None
    agent_type: str | None = None
    project_id: UUID | None = None
    instructions: str | None = None
    capability_keys: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    task_types: list[str] = Field(default_factory=list)
    element_types: list[str] = Field(default_factory=list)
    supported_codes: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    change_summary: str | None = None


class ConfigureAgentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    purpose: str | None = None
    engineering_domain: str | None = None
    agent_type: str | None = None
    configuration: dict[str, Any] | None = None


class UpdateDraftVersionRequest(BaseModel):
    instructions: str | None = None
    configuration_metadata: dict[str, Any] | None = None
    capability_keys: list[str] | None = None


class TestAgentVersionRequest(BaseModel):
    project_id: UUID
    user_request: str = Field(..., min_length=1)


class PublishAgentVersionRequest(BaseModel):
    project_id: UUID


class RollbackAgentRequest(BaseModel):
    project_id: UUID
    target_version: int = Field(..., ge=1)


class DeactivateAgentRequest(BaseModel):
    project_id: UUID


class DuplicateAgentRequest(BaseModel):
    project_id: UUID
    name: str | None = None
    key: str | None = Field(default=None, max_length=128)


class SuccessorVersionRequest(BaseModel):
    source_version: int = Field(..., ge=1)
    change_summary: str = Field(..., min_length=1)
    instructions: str | None = None


class EnableAgentRequest(BaseModel):
    project_id: UUID
    target_version: int = Field(..., ge=1)


class AgentBuilderValidationIssueResponse(BaseModel):
    code: str
    message: str
    severity: str

    @classmethod
    def from_domain(cls, issue: AgentBuilderValidationIssue) -> AgentBuilderValidationIssueResponse:
        return cls.model_validate(issue.model_dump())


class AgentBuilderValidationResponse(BaseModel):
    valid: bool
    issues: list[AgentBuilderValidationIssueResponse] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, result: AgentBuilderValidationResult) -> AgentBuilderValidationResponse:
        return cls(
            valid=result.valid,
            issues=[AgentBuilderValidationIssueResponse.from_domain(issue) for issue in result.issues],
        )


class AgentBuilderDetailResponse(BaseModel):
    agent: AgentDefinitionResponse
    version: AgentVersionResponse
    validation: AgentBuilderValidationResponse
    lifecycle: str

    @classmethod
    def from_domain(cls, detail: AgentBuilderVersionDetail) -> AgentBuilderDetailResponse:
        return cls(
            agent=AgentDefinitionResponse.from_domain(detail.definition),
            version=AgentVersionResponse.from_detail(
                detail.version.version,
                detail.version.capabilities,
            ),
            validation=AgentBuilderValidationResponse.from_domain(detail.validation),
            lifecycle=detail.lifecycle.value,
        )


class AgentVersionTestResponse(BaseModel):
    id: UUID
    agent_definition_id: UUID
    agent_version: int
    project_id: UUID
    test_input: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    validation_status: str | None = None
    errors: list[str] = Field(default_factory=list)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime

    @classmethod
    def from_domain(cls, record: AgentVersionTestRecord) -> AgentVersionTestResponse:
        return cls.model_validate(record.model_dump())


class AgentBuilderPublicationResponse(BaseModel):
    id: UUID
    agent_definition_id: UUID
    agent_version: int
    project_id: UUID | None = None
    action: str
    status: str
    approval_request_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime

    @classmethod
    def from_domain(cls, record: AgentBuilderPublicationRecord) -> AgentBuilderPublicationResponse:
        return cls.model_validate(record.model_dump())


class AgentVersionTestListResponse(BaseModel):
    tests: list[AgentVersionTestResponse]


class AgentBuilderPublicationListResponse(BaseModel):
    publications: list[AgentBuilderPublicationResponse]
