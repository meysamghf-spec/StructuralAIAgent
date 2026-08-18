"""PostgreSQL implementation of RevisionRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.revision import Revision, RevisionChangeType
from app.infrastructure.database.connection import get_connection


class PostgresRevisionRepository:
    def get_next_revision_number(self, project_id: UUID) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(revision_number), 0) + 1 AS next_revision
                    FROM revisions
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
                row = cur.fetchone()
        assert row is not None
        return int(row["next_revision"])

    def create(
        self,
        project_id: UUID,
        change_type: RevisionChangeType,
        summary: str,
        after_snapshot_id: UUID,
        *,
        before_snapshot_id: UUID | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> Revision:
        revision_number = self.get_next_revision_number(project_id)
        metadata_payload = metadata or {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO revisions (
                        project_id,
                        revision_number,
                        change_type,
                        summary,
                        before_snapshot_id,
                        after_snapshot_id,
                        created_by,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING
                        id,
                        project_id,
                        revision_number,
                        change_type,
                        summary,
                        before_snapshot_id,
                        after_snapshot_id,
                        created_by,
                        metadata,
                        created_at
                    """,
                    (
                        project_id,
                        revision_number,
                        change_type.value,
                        summary,
                        before_snapshot_id,
                        after_snapshot_id,
                        created_by,
                        json.dumps(metadata_payload),
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        row["change_type"] = RevisionChangeType(row["change_type"])
        return Revision.model_validate(row)

    def list_for_project(self, project_id: UUID) -> list[Revision]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        revision_number,
                        change_type,
                        summary,
                        before_snapshot_id,
                        after_snapshot_id,
                        created_by,
                        metadata,
                        created_at
                    FROM revisions
                    WHERE project_id = %s
                    ORDER BY revision_number ASC
                    """,
                    (project_id,),
                )
                rows = cur.fetchall()
        revisions: list[Revision] = []
        for row in rows:
            row["change_type"] = RevisionChangeType(row["change_type"])
            revisions.append(Revision.model_validate(row))
        return revisions

    def get_by_revision_number(
        self, project_id: UUID, revision_number: int
    ) -> Revision | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        revision_number,
                        change_type,
                        summary,
                        before_snapshot_id,
                        after_snapshot_id,
                        created_by,
                        metadata,
                        created_at
                    FROM revisions
                    WHERE project_id = %s AND revision_number = %s
                    """,
                    (project_id, revision_number),
                )
                row = cur.fetchone()
        if not row:
            return None
        row["change_type"] = RevisionChangeType(row["change_type"])
        return Revision.model_validate(row)
