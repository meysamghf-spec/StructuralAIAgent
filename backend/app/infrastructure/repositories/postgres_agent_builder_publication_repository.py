"""PostgreSQL implementation of AgentBuilderPublicationRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.agent_builder import AgentBuilderPublicationRecord
from app.infrastructure.database.connection import get_connection


class PostgresAgentBuilderPublicationRepository:
    def create(
        self,
        *,
        agent_definition_id: UUID,
        agent_version: int,
        action: str,
        status: str,
        project_id: UUID | None = None,
        approval_request_id: UUID | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> AgentBuilderPublicationRecord:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_builder_publications (
                        agent_definition_id,
                        agent_version,
                        project_id,
                        action,
                        status,
                        approval_request_id,
                        metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    RETURNING
                        id,
                        agent_definition_id,
                        agent_version,
                        project_id,
                        action,
                        status,
                        approval_request_id,
                        metadata,
                        created_by,
                        created_at
                    """,
                    (
                        agent_definition_id,
                        agent_version,
                        project_id,
                        action,
                        status,
                        approval_request_id,
                        json.dumps(metadata or {}),
                        created_by,
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        return AgentBuilderPublicationRecord.model_validate(row)

    def update_status(
        self,
        publication_id: UUID,
        *,
        status: str,
        metadata: dict | None = None,
    ) -> AgentBuilderPublicationRecord | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if metadata is not None:
                    cur.execute(
                        """
                        UPDATE agent_builder_publications
                        SET status = %s, metadata = metadata || %s::jsonb
                        WHERE id = %s
                        RETURNING
                            id,
                            agent_definition_id,
                            agent_version,
                            project_id,
                            action,
                            status,
                            approval_request_id,
                            metadata,
                            created_by,
                            created_at
                        """,
                        (status, json.dumps(metadata), publication_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE agent_builder_publications
                        SET status = %s
                        WHERE id = %s
                        RETURNING
                            id,
                            agent_definition_id,
                            agent_version,
                            project_id,
                            action,
                            status,
                            approval_request_id,
                            metadata,
                            created_by,
                            created_at
                        """,
                        (status, publication_id),
                    )
                row = cur.fetchone()
        if not row:
            return None
        return AgentBuilderPublicationRecord.model_validate(row)

    def get_by_approval_request_id(
        self,
        approval_request_id: UUID,
    ) -> AgentBuilderPublicationRecord | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_definition_id,
                        agent_version,
                        project_id,
                        action,
                        status,
                        approval_request_id,
                        metadata,
                        created_by,
                        created_at
                    FROM agent_builder_publications
                    WHERE approval_request_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (approval_request_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return AgentBuilderPublicationRecord.model_validate(row)

    def list_for_definition(
        self,
        agent_definition_id: UUID,
        *,
        limit: int = 50,
    ) -> list[AgentBuilderPublicationRecord]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_definition_id,
                        agent_version,
                        project_id,
                        action,
                        status,
                        approval_request_id,
                        metadata,
                        created_by,
                        created_at
                    FROM agent_builder_publications
                    WHERE agent_definition_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (agent_definition_id, limit),
                )
                rows = cur.fetchall()
        return [AgentBuilderPublicationRecord.model_validate(row) for row in rows]
