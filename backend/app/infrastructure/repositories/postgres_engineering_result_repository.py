"""PostgreSQL persistence for validated engineering result sets."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.engineering_results import EngineeringResultSet, ResultValidationStatus
from app.infrastructure.database.connection import get_connection


class PostgresEngineeringResultRepository:
    def create_result_set(
        self,
        project_id: UUID,
        *,
        analysis_run_id: UUID | None,
        integration_execution_id: UUID | None,
        pem_snapshot_id: UUID,
        pem_version: int,
        software: str,
        software_version: str,
        analysis_type: str,
        validation_status: ResultValidationStatus,
        engineering_results_available: bool,
        result_types: list[str],
        results: dict,
        provenance: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> EngineeringResultSet:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO engineering_result_sets (
                        project_id,
                        analysis_run_id,
                        integration_execution_id,
                        pem_snapshot_id,
                        pem_version,
                        software,
                        software_version,
                        analysis_type,
                        validation_status,
                        engineering_results_available,
                        result_types,
                        results,
                        provenance,
                        validation_summary,
                        metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                    RETURNING
                        id,
                        project_id,
                        analysis_run_id,
                        integration_execution_id,
                        pem_snapshot_id,
                        pem_version,
                        software,
                        software_version,
                        analysis_type,
                        validation_status,
                        engineering_results_available,
                        result_types,
                        results,
                        provenance,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at
                    """,
                    (
                        project_id,
                        analysis_run_id,
                        integration_execution_id,
                        pem_snapshot_id,
                        pem_version,
                        software,
                        software_version,
                        analysis_type,
                        validation_status.value,
                        engineering_results_available,
                        json.dumps(result_types),
                        json.dumps(results),
                        json.dumps(provenance or {}),
                        json.dumps(validation_summary or {}),
                        json.dumps(metadata or {}),
                        created_by,
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_result_set(row)

    def get_result_set(self, project_id: UUID, result_set_id: UUID) -> EngineeringResultSet | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        analysis_run_id,
                        integration_execution_id,
                        pem_snapshot_id,
                        pem_version,
                        software,
                        software_version,
                        analysis_type,
                        validation_status,
                        engineering_results_available,
                        result_types,
                        results,
                        provenance,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at
                    FROM engineering_result_sets
                    WHERE project_id = %s AND id = %s
                    """,
                    (project_id, result_set_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_result_set(row)

    def list_result_sets(
        self,
        project_id: UUID,
        *,
        analysis_run_id: UUID | None = None,
        limit: int = 50,
    ) -> list[EngineeringResultSet]:
        query = """
            SELECT
                id,
                project_id,
                analysis_run_id,
                integration_execution_id,
                pem_snapshot_id,
                pem_version,
                software,
                software_version,
                analysis_type,
                validation_status,
                engineering_results_available,
                result_types,
                results,
                provenance,
                validation_summary,
                metadata,
                created_by,
                created_at
            FROM engineering_result_sets
            WHERE project_id = %s
        """
        params: list[object] = [project_id]
        if analysis_run_id is not None:
            query += " AND analysis_run_id = %s"
            params.append(analysis_run_id)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        return [self._row_to_result_set(row) for row in rows]

    def get_validated_result_for_analysis(
        self,
        project_id: UUID,
        analysis_run_id: UUID,
    ) -> EngineeringResultSet | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        analysis_run_id,
                        integration_execution_id,
                        pem_snapshot_id,
                        pem_version,
                        software,
                        software_version,
                        analysis_type,
                        validation_status,
                        engineering_results_available,
                        result_types,
                        results,
                        provenance,
                        validation_summary,
                        metadata,
                        created_by,
                        created_at
                    FROM engineering_result_sets
                    WHERE project_id = %s
                      AND analysis_run_id = %s
                      AND engineering_results_available = TRUE
                      AND validation_status = 'VALIDATED'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (project_id, analysis_run_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_result_set(row)

    @staticmethod
    def _row_to_result_set(row) -> EngineeringResultSet:
        payload = dict(row)
        payload["validation_status"] = ResultValidationStatus(payload["validation_status"])
        return EngineeringResultSet.model_validate(payload)
