"""Agent API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.agent import (
    AgentCapability,
    AgentDefinition,
    AgentDefinitionStatus,
    AgentVersion,
    AgentVersionStatus,
    EngineeringAgentType,
)


class CreateAgentRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    agent_type: EngineeringAgentType | None = None
    project_id: UUID | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


class AgentDefinitionResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None = None
    agent_type: EngineeringAgentType | None = None
    project_id: UUID | None = None
    status: AgentDefinitionStatus
    current_version: int | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, definition: AgentDefinition) -> AgentDefinitionResponse:
        return cls.model_validate(definition.model_dump())


class AgentListResponse(BaseModel):
    agents: list[AgentDefinitionResponse]


class AgentCapabilityResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_domain(cls, capability: AgentCapability) -> AgentCapabilityResponse:
        return cls.model_validate(capability.model_dump())


class AgentVersionResponse(BaseModel):
    id: UUID
    agent_definition_id: UUID
    version: int
    instructions: str | None = None
    configuration_metadata: dict[str, Any] = Field(default_factory=dict)
    status: AgentVersionStatus
    created_at: datetime
    created_by: str | None = None
    capabilities: list[AgentCapabilityResponse] = Field(default_factory=list)

    @classmethod
    def from_detail(cls, version: AgentVersion, capabilities: list[AgentCapability]) -> AgentVersionResponse:
        payload = version.model_dump()
        payload["capabilities"] = [
            AgentCapabilityResponse.from_domain(capability).model_dump()
            for capability in capabilities
        ]
        return cls.model_validate(payload)


class CreateAgentVersionRequest(BaseModel):
    instructions: str | None = None
    configuration_metadata: dict[str, Any] = Field(default_factory=dict)
    capability_keys: list[str] = Field(default_factory=list)


class AgentVersionListResponse(BaseModel):
    versions: list[AgentVersionResponse]
