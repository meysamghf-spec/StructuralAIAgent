"""PostgreSQL implementation of AgentVersionRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.agent import AgentVersion, AgentVersionStatus
from app.infrastructure.database.connection import get_connection


class PostgresAgentVersionRepository:
    def create(
        self,
        agent_definition_id: UUID,
        *,
        version: int | None = None,
        instructions: str | None = None,
        configuration_metadata: dict | None = None,
        created_by: str | None = None,
        status: AgentVersionStatus = AgentVersionStatus.DRAFT,
    ) -> AgentVersion:
        metadata_payload = configuration_metadata or {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                if version is None:
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                        FROM agent_versions
                        WHERE agent_definition_id = %s
                        """,
                        (agent_definition_id,),
                    )
                    row = cur.fetchone()
                    assert row is not None
                    version = int(row["next_version"])

                cur.execute(
                    """
                    INSERT INTO agent_versions (
                        agent_definition_id,
                        version,
                        instructions,
                        configuration_metadata,
                        status,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING
                        id,
                        agent_definition_id,
                        version,
                        instructions,
                        configuration_metadata,
                        status,
                        created_at,
                        created_by
                    """,
                    (
                        agent_definition_id,
                        version,
                        instructions,
                        json.dumps(metadata_payload),
                        status.value,
                        created_by,
                    ),
                )
                inserted = cur.fetchone()
        assert inserted is not None
        inserted["status"] = AgentVersionStatus(inserted["status"])
        return AgentVersion.model_validate(inserted)

    def get_by_id(self, version_id: UUID) -> AgentVersion | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_definition_id,
                        version,
                        instructions,
                        configuration_metadata,
                        status,
                        created_at,
                        created_by
                    FROM agent_versions
                    WHERE id = %s
                    """,
                    (version_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentVersionStatus(row["status"])
        return AgentVersion.model_validate(row)

    def get_by_definition_and_version(
        self, agent_definition_id: UUID, version: int
    ) -> AgentVersion | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_definition_id,
                        version,
                        instructions,
                        configuration_metadata,
                        status,
                        created_at,
                        created_by
                    FROM agent_versions
                    WHERE agent_definition_id = %s AND version = %s
                    """,
                    (agent_definition_id, version),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentVersionStatus(row["status"])
        return AgentVersion.model_validate(row)

    def list_for_definition(self, agent_definition_id: UUID) -> list[AgentVersion]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_definition_id,
                        version,
                        instructions,
                        configuration_metadata,
                        status,
                        created_at,
                        created_by
                    FROM agent_versions
                    WHERE agent_definition_id = %s
                    ORDER BY version ASC
                    """,
                    (agent_definition_id,),
                )
                rows = cur.fetchall()
        versions: list[AgentVersion] = []
        for row in rows:
            row["status"] = AgentVersionStatus(row["status"])
            versions.append(AgentVersion.model_validate(row))
        return versions

    def get_active_for_definition(
        self, agent_definition_id: UUID
    ) -> AgentVersion | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_definition_id,
                        version,
                        instructions,
                        configuration_metadata,
                        status,
                        created_at,
                        created_by
                    FROM agent_versions
                    WHERE agent_definition_id = %s AND status = %s
                    LIMIT 1
                    """,
                    (agent_definition_id, AgentVersionStatus.ACTIVE.value),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentVersionStatus(row["status"])
        return AgentVersion.model_validate(row)

    def update_status(
        self, version_id: UUID, status: AgentVersionStatus
    ) -> AgentVersion | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_versions
                    SET status = %s
                    WHERE id = %s
                    RETURNING
                        id,
                        agent_definition_id,
                        version,
                        instructions,
                        configuration_metadata,
                        status,
                        created_at,
                        created_by
                    """,
                    (status.value, version_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = AgentVersionStatus(row["status"])
        return AgentVersion.model_validate(row)

    def archive_active_for_definition(self, agent_definition_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_versions
                    SET status = %s
                    WHERE agent_definition_id = %s AND status = %s
                    """,
                    (
                        AgentVersionStatus.ARCHIVED.value,
                        agent_definition_id,
                        AgentVersionStatus.ACTIVE.value,
                    ),
                )
