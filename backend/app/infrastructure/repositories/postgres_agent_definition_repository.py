"""PostgreSQL implementation of AgentDefinitionRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.agent import AgentDefinition, AgentDefinitionStatus, EngineeringAgentType
from app.infrastructure.database.connection import get_connection

_DEFINITION_COLUMNS = """
    id, key, name, description, agent_type, status,
    current_version, configuration, created_at, updated_at
"""


def _row_to_definition(row: dict) -> AgentDefinition:
    payload = dict(row)
    payload["status"] = AgentDefinitionStatus(payload["status"])
    if payload.get("agent_type"):
        payload["agent_type"] = EngineeringAgentType(payload["agent_type"])
    return AgentDefinition.model_validate(payload)


class PostgresAgentDefinitionRepository:
    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        agent_type: EngineeringAgentType | None = None,
        configuration: dict | None = None,
    ) -> AgentDefinition:
        config_payload = configuration or {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO agent_definitions (
                        key, name, description, agent_type, status, configuration
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING {_DEFINITION_COLUMNS}
                    """,
                    (
                        key,
                        name,
                        description,
                        agent_type.value if agent_type else None,
                        AgentDefinitionStatus.DRAFT.value,
                        json.dumps(config_payload),
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        return _row_to_definition(row)

    def get_by_id(self, agent_id: UUID) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_DEFINITION_COLUMNS}
                    FROM agent_definitions
                    WHERE id = %s
                    """,
                    (agent_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_definition(row)

    def get_by_key(self, key: str) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_DEFINITION_COLUMNS}
                    FROM agent_definitions
                    WHERE key = %s
                    """,
                    (key,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_definition(row)

    def get_by_agent_type(self, agent_type: EngineeringAgentType) -> AgentDefinition | None:
        agents = self.list_by_agent_type(agent_type)
        if not agents:
            return None
        active = [item for item in agents if item.status == AgentDefinitionStatus.ACTIVE]
        if active:
            return active[0]
        return agents[0]

    def list_all(self) -> list[AgentDefinition]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_DEFINITION_COLUMNS}
                    FROM agent_definitions
                    ORDER BY created_at ASC
                    """
                )
                rows = cur.fetchall()
        return [_row_to_definition(row) for row in rows]

    def list_by_agent_type(self, agent_type: EngineeringAgentType) -> list[AgentDefinition]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_DEFINITION_COLUMNS}
                    FROM agent_definitions
                    WHERE agent_type = %s
                    ORDER BY created_at ASC
                    """,
                    (agent_type.value,),
                )
                rows = cur.fetchall()
        return [_row_to_definition(row) for row in rows]

    def update_status(
        self, agent_id: UUID, status: AgentDefinitionStatus
    ) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE agent_definitions
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING {_DEFINITION_COLUMNS}
                    """,
                    (status.value, agent_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_definition(row)

    def set_current_version(
        self, agent_id: UUID, version: int | None
    ) -> AgentDefinition | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE agent_definitions
                    SET current_version = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING {_DEFINITION_COLUMNS}
                    """,
                    (version, agent_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_definition(row)
