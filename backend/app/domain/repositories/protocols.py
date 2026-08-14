"""Repository interfaces — domain layer does not depend on PostgreSQL."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.project import Project
from app.domain.models.revision import Revision, RevisionChangeType


class ProjectRepository(Protocol):
    def create(self, name: str, description: str | None = None) -> Project: ...

    def get_by_id(self, project_id: UUID) -> Project | None: ...

    def list_all(self) -> list[Project]: ...


class PemRepository(Protocol):
    def save_snapshot(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
        *,
        version: int | None = None,
        set_current: bool = True,
    ) -> tuple[UUID, int]: ...

    def get_current(self, project_id: UUID) -> ProjectEngineeringModel | None: ...

    def get_snapshot_by_version(
        self, project_id: UUID, version: int
    ) -> ProjectEngineeringModel | None: ...

    def list_versions(self, project_id: UUID) -> list[int]: ...


class RevisionRepository(Protocol):
    def create(
        self,
        project_id: UUID,
        change_type: RevisionChangeType,
        summary: str,
        after_snapshot_id: UUID,
        *,
        before_snapshot_id: UUID | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> Revision: ...

    def list_for_project(self, project_id: UUID) -> list[Revision]: ...

    def get_next_revision_number(self, project_id: UUID) -> int: ...
