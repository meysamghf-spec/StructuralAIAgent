"""PostgreSQL implementation of DesignRepository."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from app.domain.models.design import DesignRun, DesignStatus
from app.infrastructure.database.connection import get_connection


class PostgresDesignRepository:
    def create_run(
        self,
        project_id: UUID,
        *,
        pem_snapshot_id: UUID,
        pem_version: int,
        analysis_run_id: UUID | None,
        design_type: str,
        status: DesignStatus,
        capability_status: str,
        message: str,
        code_edition: str | None = None,
        inputs: dict | None = None,
        outputs: dict | None = None,
        model_summary: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> DesignRun:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO design_runs (
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        design_type,
                        status,
                        capability_status,
                        message,
                        code_edition,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                    RETURNING
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        design_type,
                        status,
                        capability_status,
                        message,
                        code_edition,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    """,
                    (
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        design_type,
                        status.value,
                        capability_status,
                        message,
                        code_edition,
                        json.dumps(inputs or {}),
                        json.dumps(outputs or {}),
                        json.dumps(model_summary or {}),
                        json.dumps(validation_summary or {}),
                        json.dumps(metadata or {}),
                        created_by,
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_run(row)

    def update_run(
        self,
        project_id: UUID,
        run_id: UUID,
        *,
        status: DesignStatus,
        capability_status: str,
        message: str,
        outputs: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        completed_at: datetime | None = None,
    ) -> DesignRun | None:
        completed = completed_at
        if completed is None and status not in {DesignStatus.CREATED, DesignStatus.RUNNING}:
            completed = datetime.now(UTC)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE design_runs
                    SET
                        status = %s,
                        capability_status = %s,
                        message = %s,
                        outputs = COALESCE(%s::jsonb, outputs),
                        validation_summary = COALESCE(%s::jsonb, validation_summary),
                        metadata = COALESCE(%s::jsonb, metadata),
                        completed_at = COALESCE(%s, completed_at)
                    WHERE project_id = %s AND id = %s
                    RETURNING
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        design_type,
                        status,
                        capability_status,
                        message,
                        code_edition,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    """,
                    (
                        status.value,
                        capability_status,
                        message,
                        json.dumps(outputs) if outputs is not None else None,
                        json.dumps(validation_summary) if validation_summary is not None else None,
                        json.dumps(metadata) if metadata is not None else None,
                        completed,
                        project_id,
                        run_id,
                    ),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_run(row)

    def get_run(self, project_id: UUID, run_id: UUID) -> DesignRun | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        design_type,
                        status,
                        capability_status,
                        message,
                        code_edition,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    FROM design_runs
                    WHERE project_id = %s AND id = %s
                    """,
                    (project_id, run_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs(
        self,
        project_id: UUID,
        *,
        limit: int = 50,
    ) -> list[DesignRun]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        design_type,
                        status,
                        capability_status,
                        message,
                        code_edition,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    FROM design_runs
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (project_id, limit),
                )
                rows = cur.fetchall()

        return [self._row_to_run(row) for row in rows]

    @staticmethod
    def _row_to_run(row) -> DesignRun:
        payload = dict(row)
        payload["status"] = DesignStatus(payload["status"])
        return DesignRun.model_validate(payload)
