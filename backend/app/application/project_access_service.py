"""Project ownership authorization."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import ProjectAuthorizationError, ProjectNotFoundError
from app.domain.models.project import Project
from app.domain.models.user import AuthenticatedAccount
from app.domain.repositories.protocols import ProjectRepository
from app.infrastructure.config import get_settings


class ProjectAccessService:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self._projects = project_repository

    @property
    def enforcement_enabled(self) -> bool:
        return get_settings().project_access_enforced

    def require_project(
        self,
        project_id: UUID,
        account: AuthenticatedAccount,
    ) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        if not self.enforcement_enabled:
            return project
        if project.owner_account_id != account.account_id:
            raise ProjectAuthorizationError(project_id, account.account_id)
        return project

    def list_accessible_projects(self, account: AuthenticatedAccount) -> list[Project]:
        if not self.enforcement_enabled:
            return self._projects.list_all()
        return self._projects.list_for_owner(account.account_id)
