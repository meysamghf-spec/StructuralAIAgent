"""Repository interfaces - domain layer does not depend on PostgreSQL."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.pem import PemSnapshotMeta, ProjectEngineeringModel
from app.domain.models.project import Project
from app.domain.models.project_memory import MemoryType, ProjectMemory
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

    def get_current_snapshot_meta(self, project_id: UUID) -> PemSnapshotMeta | None: ...

    def get_snapshot_meta_by_version(
        self, project_id: UUID, version: int
    ) -> PemSnapshotMeta | None: ...


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

    def get_by_revision_number(
        self, project_id: UUID, revision_number: int
    ) -> Revision | None: ...


class ProjectMemoryRepository(Protocol):
    def create(
        self,
        project_id: UUID,
        memory_type: MemoryType,
        content: str,
        *,
        source_type: str | None = None,
        source_id: UUID | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> ProjectMemory: ...

    def get_by_id(
        self,
        project_id: UUID,
        memory_id: UUID,
    ) -> ProjectMemory | None: ...

    def list_for_project(
        self,
        project_id: UUID,
    ) -> list[ProjectMemory]: ...

    def list_by_type(
        self,
        project_id: UUID,
        memory_type: MemoryType,
    ) -> list[ProjectMemory]: ...

    def search(
        self,
        project_id: UUID,
        *,
        source_type: str | None = None,
        source_id: UUID | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[ProjectMemory]: ...

    def delete(
        self,
        project_id: UUID,
        memory_id: UUID,
    ) -> bool: ...
