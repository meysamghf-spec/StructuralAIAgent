"""PostgreSQL implementation of AgentCapabilityRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.agent import AgentCapability
from app.infrastructure.database.connection import get_connection


class PostgresAgentCapabilityRepository:
    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> AgentCapability:
        metadata_payload = metadata or {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_capabilities (key, name, description, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
                    RETURNING id, key, name, description, metadata, created_at
                    """,
                    (key, name, description, json.dumps(metadata_payload)),
                )
                row = cur.fetchone()
        assert row is not None
        return AgentCapability.model_validate(row)

    def get_by_key(self, key: str) -> AgentCapability | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, key, name, description, metadata, created_at
                    FROM agent_capabilities
                    WHERE key = %s
                    """,
                    (key,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return AgentCapability.model_validate(row)

    def get_by_id(self, capability_id: UUID) -> AgentCapability | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, key, name, description, metadata, created_at
                    FROM agent_capabilities
                    WHERE id = %s
                    """,
                    (capability_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return AgentCapability.model_validate(row)

    def list_all(self) -> list[AgentCapability]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, key, name, description, metadata, created_at
                    FROM agent_capabilities
                    ORDER BY key ASC
                    """
                )
                rows = cur.fetchall()
        return [AgentCapability.model_validate(row) for row in rows]

    def assign_to_version(self, agent_version_id: UUID, capability_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_version_capabilities (agent_version_id, capability_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (agent_version_id, capability_id),
                )

    def list_for_version(self, agent_version_id: UUID) -> list[AgentCapability]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.key, c.name, c.description, c.metadata, c.created_at
                    FROM agent_capabilities c
                    INNER JOIN agent_version_capabilities avc
                        ON avc.capability_id = c.id
                    WHERE avc.agent_version_id = %s
                    ORDER BY c.key ASC
                    """,
                    (agent_version_id,),
                )
                rows = cur.fetchall()
        return [AgentCapability.model_validate(row) for row in rows]
