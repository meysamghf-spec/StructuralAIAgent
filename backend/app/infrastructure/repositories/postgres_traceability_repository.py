"""PostgreSQL implementation of TraceabilityRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.traceability import TraceabilityLink, TraceabilityRelationshipType
from app.infrastructure.database.connection import get_connection


class PostgresTraceabilityRepository:
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
        metadata_payload = metadata or {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO traceability_links (
                        project_id,
                        source_type,
                        source_id,
                        target_type,
                        target_id,
                        relationship_type,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING
                        id,
                        project_id,
                        source_type,
                        source_id,
                        target_type,
                        target_id,
                        relationship_type,
                        metadata,
                        created_at
                    """,
                    (
                        project_id,
                        source_type,
                        source_id,
                        target_type,
                        target_id,
                        relationship_type.value,
                        json.dumps(metadata_payload),
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_link(row)

    def get_links_by_source(
        self,
        project_id: UUID,
        *,
        source_type: str,
        source_id: UUID,
    ) -> list[TraceabilityLink]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        source_type,
                        source_id,
                        target_type,
                        target_id,
                        relationship_type,
                        metadata,
                        created_at
                    FROM traceability_links
                    WHERE project_id = %s
                      AND source_type = %s
                      AND source_id = %s
                    ORDER BY created_at ASC
                    """,
                    (project_id, source_type, source_id),
                )
                rows = cur.fetchall()

        return [self._row_to_link(row) for row in rows]

    def get_links_by_target(
        self,
        project_id: UUID,
        *,
        target_type: str,
        target_id: UUID,
    ) -> list[TraceabilityLink]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        source_type,
                        source_id,
                        target_type,
                        target_id,
                        relationship_type,
                        metadata,
                        created_at
                    FROM traceability_links
                    WHERE project_id = %s
                      AND target_type = %s
                      AND target_id = %s
                    ORDER BY created_at ASC
                    """,
                    (project_id, target_type, target_id),
                )
                rows = cur.fetchall()

        return [self._row_to_link(row) for row in rows]

    def list_for_project(self, project_id: UUID) -> list[TraceabilityLink]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        source_type,
                        source_id,
                        target_type,
                        target_id,
                        relationship_type,
                        metadata,
                        created_at
                    FROM traceability_links
                    WHERE project_id = %s
                    ORDER BY created_at ASC
                    """,
                    (project_id,),
                )
                rows = cur.fetchall()

        return [self._row_to_link(row) for row in rows]

    @staticmethod
    def _row_to_link(row: dict) -> TraceabilityLink:
        row["relationship_type"] = TraceabilityRelationshipType(row["relationship_type"])
        return TraceabilityLink.model_validate(row)
