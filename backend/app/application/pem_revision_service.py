"""Application service — atomic PEM updates with revision traceability."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.exceptions import (
    InvalidChangeTypeError,
    PemNotFoundError,
    PemProjectMismatchError,
    ProjectNotFoundError,
)
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.revision import Revision, RevisionChangeType
from app.domain.repositories.protocols import PemRepository, ProjectRepository, RevisionRepository


@dataclass
class PemUpdateResult:
    pem_version: int
    snapshot_id: UUID
    before_snapshot_id: UUID
    revision: Revision


class PemRevisionService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        pem_repository: PemRepository,
        revision_repository: RevisionRepository,
    ) -> None:
        self._projects = project_repository
        self._pem = pem_repository
        self._revisions = revision_repository

    def update_pem(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
        *,
        change_type: RevisionChangeType,
        summary: str,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> PemUpdateResult:
        if change_type == RevisionChangeType.INITIAL:
            raise InvalidChangeTypeError(change_type.value)

        if self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id)

        if pem.project_id != project_id:
            raise PemProjectMismatchError(project_id, pem.project_id)

        current_meta = self._pem.get_current_snapshot_meta(project_id)
        if current_meta is None:
            raise PemNotFoundError(project_id)

        before_snapshot_id = current_meta.id
        after_snapshot_id, pem_version = self._pem.save_snapshot(project_id, pem)

        revision_metadata = {"snapshot_version": pem_version, **(metadata or {})}
        revision = self._revisions.create(
            project_id,
            change_type,
            summary,
            after_snapshot_id=after_snapshot_id,
            before_snapshot_id=before_snapshot_id,
            created_by=created_by,
            metadata=revision_metadata,
        )

        return PemUpdateResult(
            pem_version=pem_version,
            snapshot_id=after_snapshot_id,
            before_snapshot_id=before_snapshot_id,
            revision=revision,
        )
