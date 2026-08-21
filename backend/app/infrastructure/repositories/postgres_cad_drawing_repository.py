"""PostgreSQL persistence for CAD drawings."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from app.domain.models.cad import (
    CadDrawing,
    CadDrawingStatus,
    CadOutputFormat,
    CadValidationStatus,
)
from app.infrastructure.database.connection import get_connection


class PostgresCadDrawingRepository:
    def create_drawing(
        self,
        project_id: UUID,
        *,
        pem_snapshot_id: UUID,
        pem_version: int,
        drawing_type: str,
        output_format: CadOutputFormat,
        status: CadDrawingStatus,
        validation_status: CadValidationStatus,
        message: str,
        file_path: str | None = None,
        layer_summary: dict | None = None,
        drawing_metadata: dict | None = None,
        validation_summary: dict | None = None,
        provenance: dict | None = None,
        created_by: str | None = None,
    ) -> CadDrawing:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cad_drawings (
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        drawing_type,
                        output_format,
                        status,
                        validation_status,
                        message,
                        file_path,
                        layer_summary,
                        drawing_metadata,
                        validation_summary,
                        provenance,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                    RETURNING
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        drawing_type,
                        output_format,
                        status,
                        validation_status,
                        message,
                        file_path,
                        layer_summary,
                        drawing_metadata,
                        validation_summary,
                        provenance,
                        created_by,
                        created_at,
                        completed_at
                    """,
                    (
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        drawing_type,
                        output_format.value,
                        status.value,
                        validation_status.value,
                        message,
                        file_path,
                        json.dumps(layer_summary or {}),
                        json.dumps(drawing_metadata or {}),
                        json.dumps(validation_summary or {}),
                        json.dumps(provenance or {}),
                        created_by,
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_drawing(row)

    def update_drawing(
        self,
        project_id: UUID,
        drawing_id: UUID,
        *,
        status: CadDrawingStatus | None = None,
        validation_status: CadValidationStatus | None = None,
        message: str | None = None,
        file_path: str | None = None,
        layer_summary: dict | None = None,
        drawing_metadata: dict | None = None,
        validation_summary: dict | None = None,
        provenance: dict | None = None,
        completed_at: datetime | None = None,
    ) -> CadDrawing | None:
        fields: list[str] = []
        params: list[object] = []
        if status is not None:
            fields.append("status = %s")
            params.append(status.value)
        if validation_status is not None:
            fields.append("validation_status = %s")
            params.append(validation_status.value)
        if message is not None:
            fields.append("message = %s")
            params.append(message)
        if file_path is not None:
            fields.append("file_path = %s")
            params.append(file_path)
        if layer_summary is not None:
            fields.append("layer_summary = %s::jsonb")
            params.append(json.dumps(layer_summary))
        if drawing_metadata is not None:
            fields.append("drawing_metadata = %s::jsonb")
            params.append(json.dumps(drawing_metadata))
        if validation_summary is not None:
            fields.append("validation_summary = %s::jsonb")
            params.append(json.dumps(validation_summary))
        if provenance is not None:
            fields.append("provenance = %s::jsonb")
            params.append(json.dumps(provenance))
        if completed_at is not None:
            fields.append("completed_at = %s")
            params.append(completed_at)

        if not fields:
            return self.get_drawing(project_id, drawing_id)

        params.extend([project_id, drawing_id])
        query = f"""
            UPDATE cad_drawings
            SET {", ".join(fields)}
            WHERE project_id = %s AND id = %s
            RETURNING
                id,
                project_id,
                pem_snapshot_id,
                pem_version,
                drawing_type,
                output_format,
                status,
                validation_status,
                message,
                file_path,
                layer_summary,
                drawing_metadata,
                validation_summary,
                provenance,
                created_by,
                created_at,
                completed_at
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_drawing(row)

    def get_drawing(self, project_id: UUID, drawing_id: UUID) -> CadDrawing | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        drawing_type,
                        output_format,
                        status,
                        validation_status,
                        message,
                        file_path,
                        layer_summary,
                        drawing_metadata,
                        validation_summary,
                        provenance,
                        created_by,
                        created_at,
                        completed_at
                    FROM cad_drawings
                    WHERE project_id = %s AND id = %s
                    """,
                    (project_id, drawing_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_drawing(row)

    def list_drawings(
        self,
        project_id: UUID,
        *,
        limit: int = 50,
    ) -> list[CadDrawing]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        pem_snapshot_id,
                        pem_version,
                        drawing_type,
                        output_format,
                        status,
                        validation_status,
                        message,
                        file_path,
                        layer_summary,
                        drawing_metadata,
                        validation_summary,
                        provenance,
                        created_by,
                        created_at,
                        completed_at
                    FROM cad_drawings
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (project_id, limit),
                )
                rows = cur.fetchall()

        return [self._row_to_drawing(row) for row in rows]

    @staticmethod
    def _row_to_drawing(row) -> CadDrawing:
        payload = dict(row)
        payload["output_format"] = CadOutputFormat(payload["output_format"])
        payload["status"] = CadDrawingStatus(payload["status"])
        payload["validation_status"] = CadValidationStatus(payload["validation_status"])
        return CadDrawing.model_validate(payload)
