"""PostgreSQL persistence for integration executions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from app.domain.models.integration import (
    IntegrationExecution,
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationSoftware,
)
from app.infrastructure.database.connection import get_connection


class PostgresIntegrationExecutionRepository:
    def create_execution(
        self,
        project_id: UUID,
        *,
        software: IntegrationSoftware,
        operation: IntegrationOperation,
        status: IntegrationOperationStatus,
        message: str,
        pem_snapshot_id: UUID | None = None,
        pem_version: int | None = None,
        analysis_run_id: UUID | None = None,
        inputs: dict | None = None,
        outputs: dict | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> IntegrationExecution:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integration_executions (
                        project_id,
                        software,
                        operation,
                        status,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        message,
                        inputs,
                        outputs,
                        metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                    RETURNING
                        id,
                        project_id,
                        software,
                        operation,
                        status,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        message,
                        inputs,
                        outputs,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    """,
                    (
                        project_id,
                        software.value,
                        operation.value,
                        status.value,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        message,
                        json.dumps(inputs or {}),
                        json.dumps(outputs or {}),
                        json.dumps(metadata or {}),
                        created_by,
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_execution(row)

    def update_execution(
        self,
        project_id: UUID,
        execution_id: UUID,
        *,
        status: IntegrationOperationStatus,
        message: str,
        outputs: dict | None = None,
        metadata: dict | None = None,
        analysis_run_id: UUID | None = None,
        completed_at: datetime | None = None,
    ) -> IntegrationExecution | None:
        completed = completed_at
        if completed is None:
            completed = datetime.now(UTC)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE integration_executions
                    SET
                        status = %s,
                        message = %s,
                        outputs = COALESCE(%s::jsonb, outputs),
                        metadata = COALESCE(%s::jsonb, metadata),
                        analysis_run_id = COALESCE(%s, analysis_run_id),
                        completed_at = COALESCE(%s, completed_at)
                    WHERE project_id = %s AND id = %s
                    RETURNING
                        id,
                        project_id,
                        software,
                        operation,
                        status,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        message,
                        inputs,
                        outputs,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    """,
                    (
                        status.value,
                        message,
                        json.dumps(outputs) if outputs is not None else None,
                        json.dumps(metadata) if metadata is not None else None,
                        analysis_run_id,
                        completed,
                        project_id,
                        execution_id,
                    ),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_execution(row)

    def get_execution(self, project_id: UUID, execution_id: UUID) -> IntegrationExecution | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        software,
                        operation,
                        status,
                        pem_snapshot_id,
                        pem_version,
                        analysis_run_id,
                        message,
                        inputs,
                        outputs,
                        metadata,
                        created_by,
                        created_at,
                        completed_at
                    FROM integration_executions
                    WHERE project_id = %s AND id = %s
                    """,
                    (project_id, execution_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_execution(row)

    def list_executions(
        self,
        project_id: UUID,
        *,
        software: IntegrationSoftware | None = None,
        limit: int = 50,
    ) -> list[IntegrationExecution]:
        query = """
            SELECT
                id,
                project_id,
                software,
                operation,
                status,
                pem_snapshot_id,
                pem_version,
                analysis_run_id,
                message,
                inputs,
                outputs,
                metadata,
                created_by,
                created_at,
                completed_at
            FROM integration_executions
            WHERE project_id = %s
        """
        params: list[object] = [project_id]
        if software is not None:
            query += " AND software = %s"
            params.append(software.value)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        return [self._row_to_execution(row) for row in rows]

    @staticmethod
    def _row_to_execution(row) -> IntegrationExecution:
        payload = dict(row)
        payload["software"] = IntegrationSoftware(payload["software"])
        payload["operation"] = IntegrationOperation(payload["operation"])
        payload["status"] = IntegrationOperationStatus(payload["status"])
        return IntegrationExecution.model_validate(payload)
