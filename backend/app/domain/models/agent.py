"""Agent registry domain models — platform-scoped, agent-neutral."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentDefinitionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class EngineeringAgentType(StrEnum):
    STRUCTURAL_MODELING_AGENT = "STRUCTURAL_MODELING_AGENT"
    LOAD_ASSESSMENT_AGENT = "LOAD_ASSESSMENT_AGENT"
    ANALYSIS_AGENT = "ANALYSIS_AGENT"
    CONCRETE_DESIGN_AGENT = "CONCRETE_DESIGN_AGENT"
    STEEL_DESIGN_AGENT = "STEEL_DESIGN_AGENT"
    SEISMIC_AGENT = "SEISMIC_AGENT"
    VALIDATION_AGENT = "VALIDATION_AGENT"
    CAD_AGENT = "CAD_AGENT"
    REPORTING_AGENT = "REPORTING_AGENT"
    DOCUMENT_INTERPRETATION_AGENT = "DOCUMENT_INTERPRETATION_AGENT"
    PROMPT_GENERATION_AGENT = "PROMPT_GENERATION_AGENT"


class AgentVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AgentCapability(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentDefinition(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None = None
    agent_type: EngineeringAgentType | None = None
    status: AgentDefinitionStatus = AgentDefinitionStatus.DRAFT
    current_version: int | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentVersion(BaseModel):
    id: UUID
    agent_definition_id: UUID
    version: int
    instructions: str | None = None
    configuration_metadata: dict[str, Any] = Field(default_factory=dict)
    status: AgentVersionStatus = AgentVersionStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None
