"""Traceability REST endpoints — /api/v1/traceability."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_accessible_project_from_query,
    get_current_account,
    get_project_access_service,
    get_traceability_service,
)
from app.api.schemas.traceability import (
    TraceabilityChainResponse,
    TraceabilityGraphResponse,
    TraceabilityLinkCreateRequest,
    TraceabilityLinkListResponse,
    TraceabilityLinkResponse,
)
from app.application.project_access_service import ProjectAccessService
from app.application.traceability_service import TraceabilityService
from app.domain.models.project import Project
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/traceability", tags=["traceability"])


@router.post(
    "/links",
    response_model=TraceabilityLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_traceability_link(
    body: TraceabilityLinkCreateRequest,
    traceability_service: Annotated[TraceabilityService, Depends(get_traceability_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> TraceabilityLinkResponse:
    access.require_project(body.project_id, account)
    link = traceability_service.create_link(
        body.project_id,
        source_type=body.source_type,
        source_id=body.source_id,
        target_type=body.target_type,
        target_id=body.target_id,
        relationship_type=body.relationship_type,
        metadata=body.metadata,
    )
    return TraceabilityLinkResponse.from_domain(link)


@router.get("/source", response_model=TraceabilityLinkListResponse)
def get_source_lineage(
    traceability_service: Annotated[TraceabilityService, Depends(get_traceability_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    object_type: str = Query(...),
    object_id: UUID = Query(...),
) -> TraceabilityLinkListResponse:
    links = traceability_service.get_links_by_source(
        project.id,
        source_type=object_type,
        source_id=object_id,
    )
    return TraceabilityLinkListResponse(
        links=[TraceabilityLinkResponse.from_domain(link) for link in links]
    )


@router.get("/target", response_model=TraceabilityChainResponse)
def get_target_lineage(
    traceability_service: Annotated[TraceabilityService, Depends(get_traceability_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    object_type: str = Query(...),
    object_id: UUID = Query(...),
) -> TraceabilityChainResponse:
    chain = traceability_service.query_lineage(
        project.id,
        object_type=object_type,
        object_id=object_id,
    )
    return TraceabilityChainResponse.from_domain(chain)


@router.get("/impact", response_model=TraceabilityChainResponse)
def get_impact_chain(
    traceability_service: Annotated[TraceabilityService, Depends(get_traceability_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    object_type: str = Query(...),
    object_id: UUID = Query(...),
) -> TraceabilityChainResponse:
    chain = traceability_service.query_impact_chain(
        project.id,
        object_type=object_type,
        object_id=object_id,
    )
    return TraceabilityChainResponse.from_domain(chain)


@router.get("/graph", response_model=TraceabilityGraphResponse)
def get_project_traceability_graph(
    traceability_service: Annotated[TraceabilityService, Depends(get_traceability_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
) -> TraceabilityGraphResponse:
    graph = traceability_service.get_project_graph(project.id)
    return TraceabilityGraphResponse.from_domain(graph)
