"""PostgreSQL implementation of AgentVersionTestRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.agent_builder import AgentVersionTestRecord
from app.infrastructure.database.connection import get_connection


class PostgresAgentVersionTestRepository:
    def create(
        self,
        *,
        agent_definition_id: UUID,
        agent_version: int,
        project_id: UUID,
        test_input: dict,
        result: dict,
        validation_status: str | None = None,
        errors: list[str] | None = None,
        execution_metadata: dict | None = None,
        created_by: str | None = None,
    ) -> AgentVersionTestRecord:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_version_tests (
                        agent_definition_id,
                        agent_version,
                        project_id,
                        test_input,
                        result,
                        validation_status,
                        errors,
                        execution_metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s)
                    RETURNING
                        id,
                        agent_definition_id,
                        agent_version,
                        project_id,
                        test_input,
                        result,
                        validation_status,
                        errors,
                        execution_metadata,
                        created_by,
                        created_at
                    """,
                    (
                        agent_definition_id,
                        agent_version,
                        project_id,
                        json.dumps(test_input),
                        json.dumps(result),
                        validation_status,
                        json.dumps(errors or []),
                        json.dumps(execution_metadata or {}),
                        created_by,
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        return AgentVersionTestRecord.model_validate(row)

    def list_for_version(
        self,
        agent_definition_id: UUID,
        agent_version: int,
        *,
        limit: int = 50,
    ) -> list[AgentVersionTestRecord]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_definition_id,
                        agent_version,
                        project_id,
                        test_input,
                        result,
                        validation_status,
                        errors,
                        execution_metadata,
                        created_by,
                        created_at
                    FROM agent_version_tests
                    WHERE agent_definition_id = %s AND agent_version = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (agent_definition_id, agent_version, limit),
                )
                rows = cur.fetchall()
        return [AgentVersionTestRecord.model_validate(row) for row in rows]
