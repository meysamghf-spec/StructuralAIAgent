"""PostgreSQL implementation of ReportRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.reporting import (
    Report,
    ReportOutputFormat,
    ReportStatus,
    ReportType,
    ReportVersion,
    ReportVersionStatus,
)
from app.infrastructure.database.connection import get_connection


class PostgresReportRepository:
    def create_report(
        self,
        project_id: UUID,
        *,
        report_type: ReportType,
        title: str,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> Report:
        metadata_payload = metadata or {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reports (
                        project_id,
                        report_type,
                        title,
                        metadata,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    RETURNING
                        id,
                        project_id,
                        report_type,
                        title,
                        status,
                        current_version,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    """,
                    (
                        project_id,
                        report_type.value,
                        title,
                        json.dumps(metadata_payload),
                        created_by,
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_report(row)

    def get_report(
        self,
        project_id: UUID,
        report_id: UUID,
    ) -> Report | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        report_type,
                        title,
                        status,
                        current_version,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    FROM reports
                    WHERE project_id = %s
                      AND id = %s
                    """,
                    (project_id, report_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_report(row)

    def list_reports(
        self,
        project_id: UUID,
        *,
        report_type: ReportType | None = None,
    ) -> list[Report]:
        conditions = ["project_id = %s"]
        params: list[object] = [project_id]
        if report_type is not None:
            conditions.append("report_type = %s")
            params.append(report_type.value)

        where_clause = " AND ".join(conditions)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        id,
                        project_id,
                        report_type,
                        title,
                        status,
                        current_version,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    FROM reports
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    """,
                    params,
                )
                rows = cur.fetchall()

        return [self._row_to_report(row) for row in rows]

    def update_report_status(
        self,
        project_id: UUID,
        report_id: UUID,
        *,
        status: ReportStatus,
        current_version: int | None = None,
    ) -> Report | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE reports
                    SET
                        status = %s,
                        current_version = COALESCE(%s, current_version),
                        updated_at = NOW()
                    WHERE project_id = %s
                      AND id = %s
                    RETURNING
                        id,
                        project_id,
                        report_type,
                        title,
                        status,
                        current_version,
                        metadata,
                        created_by,
                        created_at,
                        updated_at
                    """,
                    (status.value, current_version, project_id, report_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_report(row)

    def create_version(
        self,
        project_id: UUID,
        report_id: UUID,
        *,
        version: int,
        status: ReportVersionStatus,
        output_format: ReportOutputFormat,
        content: dict,
        traceability_metadata: dict,
        generated_by: str | None = None,
    ) -> ReportVersion:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO report_versions (
                        report_id,
                        project_id,
                        version,
                        status,
                        output_format,
                        content,
                        traceability_metadata,
                        generated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                    RETURNING
                        id,
                        report_id,
                        project_id,
                        version,
                        status,
                        output_format,
                        content,
                        traceability_metadata,
                        generated_at,
                        generated_by,
                        created_at
                    """,
                    (
                        report_id,
                        project_id,
                        version,
                        status.value,
                        output_format.value,
                        json.dumps(content),
                        json.dumps(traceability_metadata),
                        generated_by,
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_version(row)

    def get_version(
        self,
        project_id: UUID,
        report_id: UUID,
        version: int,
    ) -> ReportVersion | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        report_id,
                        project_id,
                        version,
                        status,
                        output_format,
                        content,
                        traceability_metadata,
                        generated_at,
                        generated_by,
                        created_at
                    FROM report_versions
                    WHERE project_id = %s
                      AND report_id = %s
                      AND version = %s
                    """,
                    (project_id, report_id, version),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_version(row)

    def get_latest_version(
        self,
        project_id: UUID,
        report_id: UUID,
    ) -> ReportVersion | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        report_id,
                        project_id,
                        version,
                        status,
                        output_format,
                        content,
                        traceability_metadata,
                        generated_at,
                        generated_by,
                        created_at
                    FROM report_versions
                    WHERE project_id = %s
                      AND report_id = %s
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (project_id, report_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_version(row)

    def list_versions(
        self,
        project_id: UUID,
        report_id: UUID,
    ) -> list[ReportVersion]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        report_id,
                        project_id,
                        version,
                        status,
                        output_format,
                        content,
                        traceability_metadata,
                        generated_at,
                        generated_by,
                        created_at
                    FROM report_versions
                    WHERE project_id = %s
                      AND report_id = %s
                    ORDER BY version ASC
                    """,
                    (project_id, report_id),
                )
                rows = cur.fetchall()

        return [self._row_to_version(row) for row in rows]

    @staticmethod
    def _row_to_report(row: dict) -> Report:
        row["report_type"] = ReportType(row["report_type"])
        row["status"] = ReportStatus(row["status"])
        return Report.model_validate(row)

    @staticmethod
    def _row_to_version(row: dict) -> ReportVersion:
        row["status"] = ReportVersionStatus(row["status"])
        row["output_format"] = ReportOutputFormat(row["output_format"])
        return ReportVersion.model_validate(row)
