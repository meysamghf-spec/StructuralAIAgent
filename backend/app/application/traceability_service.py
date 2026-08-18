"""Traceability chain application service."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import ProjectNotFoundError
from app.domain.models.traceability import (
    TraceabilityChain,
    TraceabilityGraph,
    TraceabilityLink,
    TraceabilityNode,
    TraceabilityRelationshipType,
)
from app.domain.repositories.protocols import ProjectRepository, TraceabilityRepository


class TraceabilityService:
    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        traceability_repository: TraceabilityRepository,
    ) -> None:
        self._projects = project_repository
        self._traceability = traceability_repository

    def create_link(
        self,
        project_id: UUID,
        *,
        source_type: str,
        source_id: UUID,
        target_type: str,
        target_id: UUID,
        relationship_type: TraceabilityRelationshipType,
        metadata: dict | None = None,
    ) -> TraceabilityLink:
        self._ensure_project_exists(project_id)
        return self._traceability.create_link(
            project_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            metadata=metadata,
        )

    def get_links_by_source(
        self,
        project_id: UUID,
        *,
        source_type: str,
        source_id: UUID,
    ) -> list[TraceabilityLink]:
        self._ensure_project_exists(project_id)
        return self._traceability.get_links_by_source(
            project_id,
            source_type=source_type,
            source_id=source_id,
        )

    def get_links_by_target(
        self,
        project_id: UUID,
        *,
        target_type: str,
        target_id: UUID,
    ) -> list[TraceabilityLink]:
        self._ensure_project_exists(project_id)
        return self._traceability.get_links_by_target(
            project_id,
            target_type=target_type,
            target_id=target_id,
        )

    def get_project_graph(self, project_id: UUID) -> TraceabilityGraph:
        self._ensure_project_exists(project_id)
        links = self._traceability.list_for_project(project_id)
        return TraceabilityGraph(
            project_id=project_id,
            links=links,
            nodes=self._collect_nodes(links),
        )

    def query_lineage(
        self,
        project_id: UUID,
        *,
        object_type: str,
        object_id: UUID,
    ) -> TraceabilityChain:
        self._ensure_project_exists(project_id)
        origin = TraceabilityNode(object_type=object_type, object_id=object_id)
        links = self._walk_backward(project_id, origin)
        return TraceabilityChain(
            project_id=project_id,
            origin=origin,
            links=links,
            nodes=self._collect_nodes(links, include=origin),
        )

    def query_impact_chain(
        self,
        project_id: UUID,
        *,
        object_type: str,
        object_id: UUID,
    ) -> TraceabilityChain:
        self._ensure_project_exists(project_id)
        origin = TraceabilityNode(object_type=object_type, object_id=object_id)
        links = self._walk_forward(project_id, origin)
        return TraceabilityChain(
            project_id=project_id,
            origin=origin,
            links=links,
            nodes=self._collect_nodes(links, include=origin),
        )

    def _walk_backward(
        self,
        project_id: UUID,
        origin: TraceabilityNode,
    ) -> list[TraceabilityLink]:
        collected: list[TraceabilityLink] = []
        seen_links: set[UUID] = set()
        frontier: list[TraceabilityNode] = [origin]
        seen_nodes: set[tuple[str, UUID]] = {(origin.object_type, origin.object_id)}

        while frontier:
            node = frontier.pop(0)
            incoming = self._traceability.get_links_by_target(
                project_id,
                target_type=node.object_type,
                target_id=node.object_id,
            )
            for link in incoming:
                if link.id in seen_links:
                    continue
                seen_links.add(link.id)
                collected.append(link)

                parent = TraceabilityNode(
                    object_type=link.source_type,
                    object_id=link.source_id,
                )
                key = (parent.object_type, parent.object_id)
                if key not in seen_nodes:
                    seen_nodes.add(key)
                    frontier.append(parent)

        return collected

    def _walk_forward(
        self,
        project_id: UUID,
        origin: TraceabilityNode,
    ) -> list[TraceabilityLink]:
        collected: list[TraceabilityLink] = []
        seen_links: set[UUID] = set()
        frontier: list[TraceabilityNode] = [origin]
        seen_nodes: set[tuple[str, UUID]] = {(origin.object_type, origin.object_id)}

        while frontier:
            node = frontier.pop(0)
            outgoing = self._traceability.get_links_by_source(
                project_id,
                source_type=node.object_type,
                source_id=node.object_id,
            )
            for link in outgoing:
                if link.id in seen_links:
                    continue
                seen_links.add(link.id)
                collected.append(link)

                child = TraceabilityNode(
                    object_type=link.target_type,
                    object_id=link.target_id,
                )
                key = (child.object_type, child.object_id)
                if key not in seen_nodes:
                    seen_nodes.add(key)
                    frontier.append(child)

        return collected

    @staticmethod
    def _collect_nodes(
        links: list[TraceabilityLink],
        *,
        include: TraceabilityNode | None = None,
    ) -> list[TraceabilityNode]:
        node_map: dict[tuple[str, UUID], TraceabilityNode] = {}
        if include is not None:
            node_map[(include.object_type, include.object_id)] = include

        for link in links:
            for object_type, object_id in (
                (link.source_type, link.source_id),
                (link.target_type, link.target_id),
            ):
                key = (object_type, object_id)
                if key not in node_map:
                    node_map[key] = TraceabilityNode(
                        object_type=object_type,
                        object_id=object_id,
                    )

        return list(node_map.values())

    def _ensure_project_exists(self, project_id: UUID) -> None:
        if self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id)
