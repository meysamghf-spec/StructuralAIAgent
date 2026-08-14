"""Application services — orchestrate domain persistence without leaking SQL."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.models.pem import (
    ProjectEngineeringModel,
    create_initial_pem,
)
from app.domain.models.project import Project
from app.domain.models.revision import Revision, RevisionChangeType
from app.domain.repositories.protocols import PemRepository, ProjectRepository, RevisionRepository


@dataclass
class ProjectBootstrapResult:
    project: Project
    pem: ProjectEngineeringModel
    snapshot_id: UUID
    snapshot_version: int
    revision: Revision


class ProjectService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        pem_repository: PemRepository,
        revision_repository: RevisionRepository,
    ) -> None:
        self._projects = project_repository
        self._pem = pem_repository
        self._revisions = revision_repository

    def create_project(
        self,
        name: str,
        description: str | None = None,
        *,
        created_by: str | None = None,
    ) -> ProjectBootstrapResult:
        project = self._projects.create(name=name, description=description)
        pem = create_initial_pem(project.id, name=name, description=description)
        snapshot_id, snapshot_version = self._pem.save_snapshot(project.id, pem, version=1)
        revision = self._revisions.create(
            project.id,
            RevisionChangeType.INITIAL,
            "Initial project creation with software-default PEM",
            after_snapshot_id=snapshot_id,
            created_by=created_by,
            metadata={"snapshot_version": snapshot_version},
        )
        return ProjectBootstrapResult(
            project=project,
            pem=pem,
            snapshot_id=snapshot_id,
            snapshot_version=snapshot_version,
            revision=revision,
        )

    def get_project(self, project_id: UUID) -> Project | None:
        return self._projects.get_by_id(project_id)


class PemService:
    def __init__(self, pem_repository: PemRepository) -> None:
        self._pem = pem_repository

    def get_current_pem(self, project_id: UUID) -> ProjectEngineeringModel | None:
        return self._pem.get_current(project_id)

    def save_new_version(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
    ) -> tuple[UUID, int]:
        return self._pem.save_snapshot(project_id, pem)
