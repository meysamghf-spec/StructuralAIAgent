"""Analysis engine foundation — deterministic load and result processing stubs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.exceptions import ProjectNotFoundError
from app.application.project_service import PemService, ProjectService
from app.domain.models.analysis import AnalysisRequest, AnalysisResult, AnalysisStatus


class AnalysisEngineService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service

    def run_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        if self._projects.get_project(request.project_id) is None:
            raise ProjectNotFoundError(request.project_id)

        pem = self._pem.get_current_pem(request.project_id)
        model_version = pem.id if pem else None
        return AnalysisResult(
            project_id=request.project_id,
            analysis_type=request.analysis_type,
            status=AnalysisStatus.NOT_IMPLEMENTED,
            message="Analysis engine architecture initialized; solver execution not yet connected",
            model_version_id=model_version,
            inputs=request.parameters,
            outputs={},
        )

    def summarize_load_combinations(self, project_id: UUID) -> dict[str, Any]:
        pem = self._pem.get_current_pem(project_id)
        if pem is None or self._projects.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)
        combinations = pem.analysis_models or []
        return {
            "project_id": str(project_id),
            "analysis_model_count": len(combinations),
            "load_combinations": combinations,
        }
