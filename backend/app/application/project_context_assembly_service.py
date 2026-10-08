"""Assemble scoped project context from memory, files, and PEM metadata."""

from __future__ import annotations

from uuid import UUID

from app.application.cad_generation_service import CadGenerationService
from app.application.engineering_result_service import EngineeringResultService
from app.application.exceptions import ProjectNotFoundError
from app.application.file_registry_service import FileRegistryService
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.domain.models.project_context import (
    CadDrawingSummary,
    EngineeringResultSummary,
    ProjectContextAssembly,
    ProjectFileSummary,
)
from app.domain.repositories.protocols import AnalysisRepository


class ProjectContextAssemblyService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        memory_service: ProjectMemoryService,
        file_registry_service: FileRegistryService,
        engineering_result_service: EngineeringResultService | None = None,
        analysis_repository: AnalysisRepository | None = None,
        cad_generation_service: CadGenerationService | None = None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._memory = memory_service
        self._files = file_registry_service
        self._engineering_results = engineering_result_service
        self._analysis = analysis_repository
        self._cad = cad_generation_service

    def assemble(self, project_id: UUID) -> ProjectContextAssembly:
        project = self._projects.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        memory_context = self._memory.get_project_context(project_id)
        pem_meta = self._pem.get_current_snapshot_meta(project_id)
        pem = self._pem.get_current_pem(project_id)
        files = self._files.list_project_files(project_id)

        validated_results: list[EngineeringResultSummary] = []
        if self._engineering_results is not None:
            for item in self._engineering_results.list_result_sets(project_id, limit=10):
                validated_results.append(
                    EngineeringResultSummary(
                        id=item.id,
                        analysis_run_id=item.analysis_run_id,
                        software=item.software,
                        validation_status=item.validation_status.value,
                        engineering_results_available=item.engineering_results_available,
                        result_types=item.result_types,
                    )
                )

        recent_analysis_runs: list[dict] = []
        if self._analysis is not None:
            recent_analysis_runs = [
                {
                    "id": str(run.id),
                    "analysis_type": run.analysis_type,
                    "status": run.status.value,
                    "engineering_results_available": bool(
                        run.outputs.get("engineering_results_available")
                    ),
                }
                for run in self._analysis.list_runs(project_id, limit=10)
            ]

        recent_cad_drawings: list[CadDrawingSummary] = []
        if self._cad is not None:
            for drawing in self._cad.list_drawings(project_id, limit=10):
                recent_cad_drawings.append(
                    CadDrawingSummary(
                        id=drawing.id,
                        drawing_type=drawing.drawing_type,
                        output_format=drawing.output_format.value,
                        status=drawing.status.value,
                        validation_status=drawing.validation_status.value,
                        message=drawing.message,
                    )
                )

        return ProjectContextAssembly(
            project_id=project_id,
            project_name=project.name,
            pem_version=pem_meta.version if pem_meta else None,
            pem_snapshot_id=pem_meta.id if pem_meta else None,
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
            validated_engineering_results=validated_results,
            recent_analysis_runs=recent_analysis_runs,
            recent_cad_drawings=recent_cad_drawings,
        )
