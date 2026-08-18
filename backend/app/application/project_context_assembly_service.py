"""Assemble scoped project context from memory, files, and PEM metadata."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import ProjectNotFoundError
from app.application.file_registry_service import FileRegistryService
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.domain.models.project_context import ProjectContextAssembly, ProjectFileSummary


class ProjectContextAssemblyService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        memory_service: ProjectMemoryService,
        file_registry_service: FileRegistryService,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._memory = memory_service
        self._files = file_registry_service

    def assemble(self, project_id: UUID) -> ProjectContextAssembly:
        project = self._projects.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        memory_context = self._memory.get_project_context(project_id)
        pem_meta = self._pem.get_current_snapshot_meta(project_id)
        pem = self._pem.get_current_pem(project_id)
        files = self._files.list_project_files(project_id)

        return ProjectContextAssembly(
            project_id=project_id,
            project_name=project.name,
            pem_version=pem_meta.version if pem_meta else None,
            code_configuration=pem.code_configuration if pem else None,
            unit_configuration=pem.unit_configuration if pem else None,
            memory_total_count=memory_context.total_count,
            memory_counts_by_type=memory_context.counts_by_type,
            memories=memory_context.memories,
            files=[
                ProjectFileSummary(
                    id=item.id,
                    filename=item.filename,
                    file_type=item.file_type.value,
                    parsing_status=item.parsing_status.value,
                    extraction_status=item.extraction_status.value,
                )
                for item in files
            ],
        )
