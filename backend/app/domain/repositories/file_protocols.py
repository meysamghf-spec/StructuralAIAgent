"""Project file repository interface."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.file_artifact import (
    ExtractionStatus,
    FileSource,
    FileType,
    ParsingStatus,
    ProjectFile,
)


class ProjectFileRepository(Protocol):
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
    ) -> ProjectFile: ...

    def get_by_id(self, project_id: UUID, file_id: UUID) -> ProjectFile | None: ...

    def list_for_project(self, project_id: UUID) -> list[ProjectFile]: ...

    def update_statuses(
        self,
        project_id: UUID,
        file_id: UUID,
        *,
        parsing_status: ParsingStatus | None = None,
        extraction_status: ExtractionStatus | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
    ) -> ProjectFile | None: ...

    def next_file_version(self, project_id: UUID, filename: str) -> int: ...
