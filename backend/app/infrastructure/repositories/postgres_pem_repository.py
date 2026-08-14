"""PostgreSQL implementation of PemRepository — PEM as versioned JSONB snapshots."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.pem import ProjectEngineeringModel
from app.infrastructure.database.connection import get_connection


class PostgresPemRepository:
    def save_snapshot(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
        *,
        version: int | None = None,
        set_current: bool = True,
    ) -> tuple[UUID, int]:
        pem_payload = pem.model_copy(update={"project_id": project_id})
        snapshot_json = json.loads(pem_payload.model_dump_json())

        with get_connection() as conn:
            with conn.cursor() as cur:
                if version is None:
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                        FROM pem_snapshots
                        WHERE project_id = %s
                        """,
                        (project_id,),
                    )
                    row = cur.fetchone()
                    assert row is not None
                    version = int(row["next_version"])

                if set_current:
                    cur.execute(
                        """
                        UPDATE pem_snapshots
                        SET is_current = FALSE
                        WHERE project_id = %s AND is_current = TRUE
                        """,
                        (project_id,),
                    )

                cur.execute(
                    """
                    INSERT INTO pem_snapshots (project_id, version, snapshot_data, is_current)
                    VALUES (%s, %s, %s::jsonb, %s)
                    RETURNING id, version
                    """,
                    (project_id, version, json.dumps(snapshot_json), set_current),
                )
                inserted = cur.fetchone()
        assert inserted is not None
        return UUID(str(inserted["id"])), int(inserted["version"])

    def get_current(self, project_id: UUID) -> ProjectEngineeringModel | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT snapshot_data
                    FROM pem_snapshots
                    WHERE project_id = %s AND is_current = TRUE
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (project_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return ProjectEngineeringModel.model_validate(row["snapshot_data"])

    def get_snapshot_by_version(
        self, project_id: UUID, version: int
    ) -> ProjectEngineeringModel | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT snapshot_data
                    FROM pem_snapshots
                    WHERE project_id = %s AND version = %s
                    """,
                    (project_id, version),
                )
                row = cur.fetchone()
        if not row:
            return None
        return ProjectEngineeringModel.model_validate(row["snapshot_data"])

    def list_versions(self, project_id: UUID) -> list[int]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT version
                    FROM pem_snapshots
                    WHERE project_id = %s
                    ORDER BY version ASC
                    """,
                    (project_id,),
                )
                rows = cur.fetchall()
        return [int(row["version"]) for row in rows]
