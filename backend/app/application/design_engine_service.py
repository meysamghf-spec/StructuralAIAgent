"""Design engine foundation — deterministic member design stubs."""

from __future__ import annotations

from app.application.exceptions import ProjectNotFoundError
from app.application.project_service import PemService, ProjectService
from app.domain.models.design import DesignRequest, DesignResult, DesignStatus


class DesignEngineService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service

    def run_design(self, request: DesignRequest) -> DesignResult:
        if self._projects.get_project(request.project_id) is None:
            raise ProjectNotFoundError(request.project_id)

        pem = self._pem.get_current_pem(request.project_id)
        code_edition = pem.code_configuration.steel_edition if pem else None
        return DesignResult(
            project_id=request.project_id,
            design_type=request.design_type,
            status=DesignStatus.NOT_IMPLEMENTED,
            message="Design engine architecture initialized; code checks not yet connected",
            code_edition=code_edition,
            inputs=request.parameters,
            outputs={},
        )
