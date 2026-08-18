"""PostgreSQL implementation of AgentDefinitionRepository."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.agent import AgentDefinition, AgentDefinitionStatus
from app.infrastructure.database.connection import get_connection


class PostgresAgentDefinitionRepository:
    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
    ) -> AgentDefinition:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_definitions (key, name, description, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING
                        id, key, name, description, status,
                        current_version, created_at, updated_at
                    """,
                    (key, name, description, AgentDefinitionStatus.DRAFT.value),
                )
                row = cur.fetchone()
        assert row is not None
        row["status"] = AgentDefinitionStatus(row["status"])
        return AgentDefinition.model_validate(row)

    def get_by_id(self, agent_id: UUID) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, key, name, description, status,
                           current_version, created_at, updated_at
                    FROM agent_definitions
                    WHERE id = %s
                    """,
                    (agent_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentDefinitionStatus(row["status"])
        return AgentDefinition.model_validate(row)

    def get_by_key(self, key: str) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, key, name, description, status,
                           current_version, created_at, updated_at
                    FROM agent_definitions
                    WHERE key = %s
                    """,
                    (key,),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentDefinitionStatus(row["status"])
        return AgentDefinition.model_validate(row)

    def list_all(self) -> list[AgentDefinition]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, key, name, description, status,
                           current_version, created_at, updated_at
                    FROM agent_definitions
                    ORDER BY created_at ASC
                    """
                )
                rows = cur.fetchall()
        definitions: list[AgentDefinition] = []
        for row in rows:
            row["status"] = AgentDefinitionStatus(row["status"])
            definitions.append(AgentDefinition.model_validate(row))
        return definitions

    def update_status(
        self, agent_id: UUID, status: AgentDefinitionStatus
    ) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_definitions
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING
                        id, key, name, description, status,
                        current_version, created_at, updated_at
                    """,
                    (status.value, agent_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentDefinitionStatus(row["status"])
        return AgentDefinition.model_validate(row)

    def set_current_version(
        self, agent_id: UUID, version: int | None
    ) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_definitions
                    SET current_version = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING
                        id, key, name, description, status,
                        current_version, created_at, updated_at
                    """,
                    (version, agent_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentDefinitionStatus(row["status"])
        return AgentDefinition.model_validate(row)
