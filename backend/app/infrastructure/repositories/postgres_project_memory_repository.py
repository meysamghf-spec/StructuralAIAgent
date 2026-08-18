"""PostgreSQL implementation of ProjectMemoryRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.project_memory import MemoryType, ProjectMemory
from app.infrastructure.database.connection import get_connection


class PostgresProjectMemoryRepository:
    def create(
        self,
        project_id: UUID,
        memory_type: MemoryType,
        content: str,
        *,
        source_type: str | None = None,
        source_id: UUID | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> ProjectMemory:
        metadata_payload = metadata or {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO project_memory (
                        project_id,
                        memory_type,
                        content,
                        source_type,
                        source_id,
                        confidence,
                        metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    RETURNING
                        id,
                        project_id,
                        memory_type,
                        content,
                        source_type,
                        source_id,
                        confidence,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    """,
                    (
                        project_id,
                        memory_type.value,
                        content,
                        source_type,
                        source_id,
                        confidence,
                        json.dumps(metadata_payload),
                        created_by,
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        row["memory_type"] = MemoryType(row["memory_type"])
        return ProjectMemory.model_validate(row)

    def get_by_id(
        self,
        project_id: UUID,
        memory_id: UUID,
    ) -> ProjectMemory | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        memory_type,
                        content,
                        source_type,
                        source_id,
                        confidence,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    FROM project_memory
                    WHERE project_id = %s
                      AND id = %s
                    """,
                    (project_id, memory_id),
                )
                row = cur.fetchone()

        if not row:
            return None

        row["memory_type"] = MemoryType(row["memory_type"])
        return ProjectMemory.model_validate(row)

    def list_for_project(
        self,
        project_id: UUID,
    ) -> list[ProjectMemory]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        memory_type,
                        content,
                        source_type,
                        source_id,
                        confidence,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    FROM project_memory
                    WHERE project_id = %s
                    ORDER BY created_at ASC
                    """,
                    (project_id,),
                )
                rows = cur.fetchall()

        memories: list[ProjectMemory] = []
        for row in rows:
            row["memory_type"] = MemoryType(row["memory_type"])
            memories.append(ProjectMemory.model_validate(row))

        return memories

    def list_by_type(
        self,
        project_id: UUID,
        memory_type: MemoryType,
    ) -> list[ProjectMemory]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        memory_type,
                        content,
                        source_type,
                        source_id,
                        confidence,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    FROM project_memory
                    WHERE project_id = %s
                      AND memory_type = %s
                    ORDER BY created_at ASC
                    """,
                    (project_id, memory_type.value),
                )
                rows = cur.fetchall()

        memories: list[ProjectMemory] = []
        for row in rows:
            row["memory_type"] = MemoryType(row["memory_type"])
            memories.append(ProjectMemory.model_validate(row))

        return memories

    def search(
        self,
        project_id: UUID,
        *,
        source_type: str | None = None,
        source_id: UUID | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[ProjectMemory]:
        conditions = ["project_id = %s"]
        params: list[object] = [project_id]

        if source_type is not None:
            conditions.append("source_type = %s")
            params.append(source_type)
        if source_id is not None:
            conditions.append("source_id = %s")
            params.append(source_id)
        if memory_type is not None:
            conditions.append("memory_type = %s")
            params.append(memory_type.value)

        where_clause = " AND ".join(conditions)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        id,
                        project_id,
                        memory_type,
                        content,
                        source_type,
                        source_id,
                        confidence,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    FROM project_memory
                    WHERE {where_clause}
                    ORDER BY created_at ASC
                    """,
                    params,
                )
                rows = cur.fetchall()

        return self._rows_to_memories(rows)

    @staticmethod
    def _rows_to_memories(rows: list[dict]) -> list[ProjectMemory]:
        memories: list[ProjectMemory] = []
        for row in rows:
            row["memory_type"] = MemoryType(row["memory_type"])
            memories.append(ProjectMemory.model_validate(row))
        return memories

    def delete(
        self,
        project_id: UUID,
        memory_id: UUID,
    ) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM project_memory
                    WHERE project_id = %s
                      AND id = %s
                    """,
                    (project_id, memory_id),
                )
                deleted = cur.rowcount > 0

        return deleted
