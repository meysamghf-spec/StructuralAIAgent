"""PostgreSQL implementation of PromptTemplateRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.prompt_template import PromptTemplate, PromptTemplateStatus
from app.infrastructure.database.connection import get_connection


class PostgresPromptTemplateRepository:
    def create(
        self,
        agent_version_id: UUID,
        *,
        name: str,
        template: str,
        version: int | None = None,
        variables_schema: dict | None = None,
        created_by: str | None = None,
        status: PromptTemplateStatus = PromptTemplateStatus.DRAFT,
    ) -> PromptTemplate:
        schema_payload = variables_schema or {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                if version is None:
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                        FROM prompt_templates
                        WHERE agent_version_id = %s
                        """,
                        (agent_version_id,),
                    )
                    row = cur.fetchone()
                    assert row is not None
                    version = int(row["next_version"])

                cur.execute(
                    """
                    INSERT INTO prompt_templates (
                        agent_version_id,
                        version,
                        name,
                        template,
                        variables_schema,
                        status,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING
                        id,
                        agent_version_id,
                        version,
                        name,
                        template,
                        variables_schema,
                        status,
                        created_at,
                        created_by
                    """,
                    (
                        agent_version_id,
                        version,
                        name,
                        template,
                        json.dumps(schema_payload),
                        status.value,
                        created_by,
                    ),
                )
                inserted = cur.fetchone()
        assert inserted is not None
        inserted["status"] = PromptTemplateStatus(inserted["status"])
        return PromptTemplate.model_validate(inserted)

    def get_by_version_and_number(
        self, agent_version_id: UUID, version: int
    ) -> PromptTemplate | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_version_id,
                        version,
                        name,
                        template,
                        variables_schema,
                        status,
                        created_at,
                        created_by
                    FROM prompt_templates
                    WHERE agent_version_id = %s AND version = %s
                    """,
                    (agent_version_id, version),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = PromptTemplateStatus(row["status"])
        return PromptTemplate.model_validate(row)

    def list_for_version(self, agent_version_id: UUID) -> list[PromptTemplate]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_version_id,
                        version,
                        name,
                        template,
                        variables_schema,
                        status,
                        created_at,
                        created_by
                    FROM prompt_templates
                    WHERE agent_version_id = %s
                    ORDER BY version ASC
                    """,
                    (agent_version_id,),
                )
                rows = cur.fetchall()
        templates: list[PromptTemplate] = []
        for row in rows:
            row["status"] = PromptTemplateStatus(row["status"])
            templates.append(PromptTemplate.model_validate(row))
        return templates

    def get_latest_for_version(self, agent_version_id: UUID) -> PromptTemplate | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        agent_version_id,
                        version,
                        name,
                        template,
                        variables_schema,
                        status,
                        created_at,
                        created_by
                    FROM prompt_templates
                    WHERE agent_version_id = %s
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (agent_version_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["status"] = PromptTemplateStatus(row["status"])
        return PromptTemplate.model_validate(row)
