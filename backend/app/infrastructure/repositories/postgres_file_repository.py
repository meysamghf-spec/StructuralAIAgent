"""PostgreSQL implementation of ProjectFileRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.file_artifact import (
    ExtractionStatus,
    FileSource,
    FileType,
    ParsingStatus,
    ProjectFile,
)
from app.infrastructure.database.connection import get_connection


class PostgresFileRepository:
    def create(
        self,
        *,
        file_id: UUID | None = None,
        project_id: UUID,
        filename: str,
        content_type: str | None,
        file_type: FileType,
        file_version: int | None,
        source: FileSource,
        storage_path: str,
        parsing_status: ParsingStatus,
        extraction_status: ExtractionStatus,
        confidence: float | None,
        metadata: dict | None,
        created_by: str | None,
    ) -> ProjectFile:
        version = file_version if file_version is not None else self.next_file_version(project_id, filename)
        with get_connection() as conn:
            with conn.cursor() as cur:
                if file_id is None:
                    cur.execute(
                        """
                        INSERT INTO project_files (
                            project_id, filename, content_type, file_type, file_version,
                            source, parsing_status, extraction_status, confidence,
                            storage_path, metadata, created_by
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        RETURNING
                            id, project_id, filename, content_type, file_type, file_version,
                            source, upload_time, parsing_status, extraction_status, confidence,
                            storage_path, metadata, created_by, created_at, updated_at
                        """,
                        (
                            project_id,
                            filename,
                            content_type,
                            file_type.value,
                            version,
                            source.value,
                            parsing_status.value,
                            extraction_status.value,
                            confidence,
                            storage_path,
                            json.dumps(metadata or {}),
                            created_by,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO project_files (
                            id, project_id, filename, content_type, file_type, file_version,
                            source, parsing_status, extraction_status, confidence,
                            storage_path, metadata, created_by
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        RETURNING
                            id, project_id, filename, content_type, file_type, file_version,
                            source, upload_time, parsing_status, extraction_status, confidence,
                            storage_path, metadata, created_by, created_at, updated_at
                        """,
                        (
                            file_id,
                            project_id,
                            filename,
                            content_type,
                            file_type.value,
                            version,
                            source.value,
                            parsing_status.value,
                            extraction_status.value,
                            confidence,
                            storage_path,
                            json.dumps(metadata or {}),
                            created_by,
                        ),
                    )
                row = cur.fetchone()
        assert row is not None
        return self._row_to_model(row)

    def get_by_id(self, project_id: UUID, file_id: UUID) -> ProjectFile | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id, project_id, filename, content_type, file_type, file_version,
                        source, upload_time, parsing_status, extraction_status, confidence,
                        storage_path, metadata, created_by, created_at, updated_at
                    FROM project_files
                    WHERE project_id = %s AND id = %s
                    """,
                    (project_id, file_id),
                )
                row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def list_for_project(self, project_id: UUID) -> list[ProjectFile]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id, project_id, filename, content_type, file_type, file_version,
                        source, upload_time, parsing_status, extraction_status, confidence,
                        storage_path, metadata, created_by, created_at, updated_at
                    FROM project_files
                    WHERE project_id = %s
                    ORDER BY upload_time DESC, filename ASC
                    """,
                    (project_id,),
                )
                rows = cur.fetchall()
        return [self._row_to_model(row) for row in rows]

    def update_statuses(
        self,
        project_id: UUID,
        file_id: UUID,
        *,
        parsing_status: ParsingStatus | None = None,
        extraction_status: ExtractionStatus | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
    ) -> ProjectFile | None:
        assignments: list[str] = ["updated_at = NOW()"]
        params: list[object] = []
        if parsing_status is not None:
            assignments.append("parsing_status = %s")
            params.append(parsing_status.value)
        if extraction_status is not None:
            assignments.append("extraction_status = %s")
            params.append(extraction_status.value)
        if confidence is not None:
            assignments.append("confidence = %s")
            params.append(confidence)
        if metadata is not None:
            assignments.append("metadata = %s::jsonb")
            params.append(json.dumps(metadata))

        params.extend([project_id, file_id])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE project_files
                    SET {", ".join(assignments)}
                    WHERE project_id = %s AND id = %s
                    RETURNING
                        id, project_id, filename, content_type, file_type, file_version,
                        source, upload_time, parsing_status, extraction_status, confidence,
                        storage_path, metadata, created_by, created_at, updated_at
                    """,
                    params,
                )
                row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def next_file_version(self, project_id: UUID, filename: str) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(file_version), 0) + 1 AS next_version
                    FROM project_files
                    WHERE project_id = %s AND filename = %s
                    """,
                    (project_id, filename),
                )
                row = cur.fetchone()
        assert row is not None
        return int(row["next_version"])

    @staticmethod
    def _row_to_model(row: dict) -> ProjectFile:
        row = dict(row)
        row["file_type"] = FileType(row["file_type"])
        row["source"] = FileSource(row["source"])
        row["parsing_status"] = ParsingStatus(row["parsing_status"])
        row["extraction_status"] = ExtractionStatus(row["extraction_status"])
        if isinstance(row.get("metadata"), str):
            row["metadata"] = json.loads(row["metadata"])
        return ProjectFile.model_validate(row)
