"""Traceability API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.traceability import (
    TraceabilityChain,
    TraceabilityGraph,
    TraceabilityLink,
    TraceabilityNode,
    TraceabilityRelationshipType,
)


class TraceabilityLinkCreateRequest(BaseModel):
    project_id: UUID
    source_type: str = Field(..., min_length=1)
    source_id: UUID
    target_type: str = Field(..., min_length=1)
    target_id: UUID
    relationship_type: TraceabilityRelationshipType
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceabilityLinkResponse(BaseModel):
    id: UUID
    project_id: UUID
    source_type: str
    source_id: UUID
    target_type: str
    target_id: UUID
    relationship_type: TraceabilityRelationshipType
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_domain(cls, link: TraceabilityLink) -> TraceabilityLinkResponse:
        return cls.model_validate(link.model_dump())


class TraceabilityNodeResponse(BaseModel):
    object_type: str
    object_id: UUID

    @classmethod
    def from_domain(cls, node: TraceabilityNode) -> TraceabilityNodeResponse:
        return cls.model_validate(node.model_dump())


class TraceabilityGraphResponse(BaseModel):
    project_id: UUID
    links: list[TraceabilityLinkResponse]
    nodes: list[TraceabilityNodeResponse]

    @classmethod
    def from_domain(cls, graph: TraceabilityGraph) -> TraceabilityGraphResponse:
        return cls(
            project_id=graph.project_id,
            links=[TraceabilityLinkResponse.from_domain(link) for link in graph.links],
            nodes=[TraceabilityNodeResponse.from_domain(node) for node in graph.nodes],
        )


class TraceabilityChainResponse(BaseModel):
    project_id: UUID
    origin: TraceabilityNodeResponse
    links: list[TraceabilityLinkResponse]
    nodes: list[TraceabilityNodeResponse]

    @classmethod
    def from_domain(cls, chain: TraceabilityChain) -> TraceabilityChainResponse:
        return cls(
            project_id=chain.project_id,
            origin=TraceabilityNodeResponse.from_domain(chain.origin),
            links=[TraceabilityLinkResponse.from_domain(link) for link in chain.links],
            nodes=[TraceabilityNodeResponse.from_domain(node) for node in chain.nodes],
        )


class TraceabilityLinkListResponse(BaseModel):
    links: list[TraceabilityLinkResponse]
