"""Project-scoped file metadata registry."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import ProjectFileNotFoundError, ProjectNotFoundError
from app.application.project_service import ProjectService
from app.domain.models.file_artifact import ProjectFile
from app.domain.repositories.file_protocols import ProjectFileRepository


class FileRegistryService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        file_repository: ProjectFileRepository,
    ) -> None:
        self._project_service = project_service
        self._file_repository = file_repository

    def list_project_files(self, project_id: UUID) -> list[ProjectFile]:
        self._ensure_project_exists(project_id)
        return self._file_repository.list_for_project(project_id)

    def get_project_file(self, project_id: UUID, file_id: UUID) -> ProjectFile:
        self._ensure_project_exists(project_id)
        record = self._file_repository.get_by_id(project_id, file_id)
        if record is None:
            raise ProjectFileNotFoundError(project_id, file_id)
        return record

    def _ensure_project_exists(self, project_id: UUID) -> None:
        if self._project_service.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)
