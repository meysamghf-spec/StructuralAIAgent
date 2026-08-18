"""Traceability chain domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TraceObjectType(StrEnum):
    REQUIREMENT = "requirement"
    FILE = "file"
    MEMORY = "memory"
    APPROVAL = "approval"
    PEM_SNAPSHOT = "pem_snapshot"
    ANALYSIS_RESULT = "analysis_result"
    DESIGN_RESULT = "design_result"
    REPORT = "report"
    USER_REQUEST = "user_request"
    AGENT_EXECUTION = "agent_execution"
    AGENT_RESULT = "agent_result"


class TraceabilityRelationshipType(StrEnum):
    REQUIREMENT_TO_SOURCE = "REQUIREMENT_TO_SOURCE"
    SOURCE_TO_MEMORY = "SOURCE_TO_MEMORY"
    MEMORY_TO_DECISION = "MEMORY_TO_DECISION"
    DECISION_TO_APPROVAL = "DECISION_TO_APPROVAL"
    APPROVAL_TO_MODEL = "APPROVAL_TO_MODEL"
    MODEL_TO_ANALYSIS = "MODEL_TO_ANALYSIS"
    ANALYSIS_TO_DESIGN = "ANALYSIS_TO_DESIGN"
    DESIGN_TO_REPORT = "DESIGN_TO_REPORT"
    REQUEST_TO_AGENT_EXECUTION = "REQUEST_TO_AGENT_EXECUTION"
    AGENT_EXECUTION_TO_RESULT = "AGENT_EXECUTION_TO_RESULT"
    AGENT_RESULT_TO_VALIDATION = "AGENT_RESULT_TO_VALIDATION"
    AGENT_RESULT_TO_APPROVAL = "AGENT_RESULT_TO_APPROVAL"
    APPROVAL_TO_AGENT_RESULT = "APPROVAL_TO_AGENT_RESULT"
    AGENT_RESULT_TO_REPORT = "AGENT_RESULT_TO_REPORT"


class TraceabilityLink(BaseModel):
    id: UUID
    project_id: UUID
    source_type: str
    source_id: UUID
    target_type: str
    target_id: UUID
    relationship_type: TraceabilityRelationshipType
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TraceabilityNode(BaseModel):
    object_type: str
    object_id: UUID


class TraceabilityGraph(BaseModel):
    project_id: UUID
    links: list[TraceabilityLink] = Field(default_factory=list)
    nodes: list[TraceabilityNode] = Field(default_factory=list)


class TraceabilityChain(BaseModel):
    project_id: UUID
    origin: TraceabilityNode
    links: list[TraceabilityLink] = Field(default_factory=list)
    nodes: list[TraceabilityNode] = Field(default_factory=list)
