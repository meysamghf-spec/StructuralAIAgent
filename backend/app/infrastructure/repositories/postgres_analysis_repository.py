"""PostgreSQL implementation of AnalysisRepository."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from app.domain.models.analysis import AnalysisRun, AnalysisStatus
from app.infrastructure.database.connection import get_connection


class PostgresAnalysisRepository:
    def create_run(
        self,
        project_id: UUID,
        *,
        pem_snapshot_id: UUID,
        pem_version: int,
        analysis_type: str,
        status: AnalysisStatus,
        capability_status: str,
        message: str,
        inputs: dict | None = None,
        outputs: dict | None = None,
        model_summary: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> AnalysisRun:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_runs (
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_type,
                        status,
                        capability_status,
                        message,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                    RETURNING
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_type,
                        status,
                        capability_status,
                        message,
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
                        analysis_type,
                        status.value,
                        capability_status,
                        message,
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
        status: AnalysisStatus,
        capability_status: str,
        message: str,
        outputs: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        completed_at: datetime | None = None,
    ) -> AnalysisRun | None:
        completed = completed_at
        if completed is None and status not in {AnalysisStatus.CREATED, AnalysisStatus.RUNNING}:
            completed = datetime.now(UTC)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_runs
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
                        analysis_type,
                        status,
                        capability_status,
                        message,
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

    def get_run(self, project_id: UUID, run_id: UUID) -> AnalysisRun | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_type,
                        status,
                        capability_status,
                        message,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    FROM analysis_runs
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
    ) -> list[AnalysisRun]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        analysis_type,
                        status,
                        capability_status,
                        message,
                        inputs,
                        outputs,
                        model_summary,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    FROM analysis_runs
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (project_id, limit),
                )
                rows = cur.fetchall()

        return [self._row_to_run(row) for row in rows]

    @staticmethod
    def _row_to_run(row) -> AnalysisRun:
        payload = dict(row)
        payload["status"] = AnalysisStatus(payload["status"])
        return AnalysisRun.model_validate(payload)
