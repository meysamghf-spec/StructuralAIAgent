"""Application service — revision queries."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import ProjectNotFoundError, RevisionNotFoundError
from app.domain.models.revision import Revision
from app.domain.repositories.protocols import ProjectRepository, RevisionRepository


class RevisionService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        revision_repository: RevisionRepository,
    ) -> None:
        self._projects = project_repository
        self._revisions = revision_repository

    def list_revisions(self, project_id: UUID) -> list[Revision]:
        if self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id)
        return self._revisions.list_for_project(project_id)

    def get_revision(self, project_id: UUID, revision_number: int) -> Revision:
        if self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id)
        revision = self._revisions.get_by_revision_number(project_id, revision_number)
        if revision is None:
            raise RevisionNotFoundError(project_id, revision_number)
        return revision
