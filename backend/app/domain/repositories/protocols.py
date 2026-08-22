"""Repository interfaces - domain layer does not depend on PostgreSQL."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.models.traceability import (
    TraceabilityGraph,
    TraceabilityLink,
    TraceabilityRelationshipType,
)
from app.domain.models.human_approval import (
    ApprovalEvent,
    ApprovalEventType,
    ApprovalStatus,
    ApprovalTargetType,
    HumanApprovalRequest,
)
from app.domain.models.pem import PemSnapshotMeta, ProjectEngineeringModel
from app.domain.models.project import Project
from app.domain.models.project_memory import MemoryType, ProjectMemory
from app.domain.models.reporting import (
    Report,
    ReportOutputFormat,
    ReportStatus,
    ReportType,
    ReportVersion,
    ReportVersionStatus,
)
from app.domain.models.analysis import AnalysisRun, AnalysisStatus
from app.domain.models.design import DesignRun, DesignStatus
from app.domain.models.optimization import OptimizationRun
from app.domain.models.revision import Revision, RevisionChangeType


class ProjectRepository(Protocol):
    def create(
        self,
        name: str,
        description: str | None = None,
        *,
        owner_account_id: str = "legacy",
    ) -> Project: ...

    def get_by_id(self, project_id: UUID) -> Project | None: ...

    def list_all(self) -> list[Project]: ...

    def list_for_owner(self, owner_account_id: str) -> list[Project]: ...


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


class HumanApprovalRepository(Protocol):
    def create_request(
        self,
        project_id: UUID,
        *,
        requester: str,
        target_type: ApprovalTargetType,
        target_action: str,
        summary: str,
        target_object_type: str | None = None,
        target_object_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> HumanApprovalRequest: ...

    def get_request(
        self,
        project_id: UUID,
        request_id: UUID,
    ) -> HumanApprovalRequest | None: ...

    def list_requests(
        self,
        project_id: UUID,
        *,
        status: ApprovalStatus | None = None,
    ) -> list[HumanApprovalRequest]: ...

    def update_request(
        self,
        project_id: UUID,
        request_id: UUID,
        *,
        status: ApprovalStatus,
        approver: str | None = None,
        decision: ApprovalStatus | None = None,
        rejection_reason: str | None = None,
        resolved_at: datetime | None = None,
    ) -> HumanApprovalRequest | None: ...

    def create_event(
        self,
        project_id: UUID,
        approval_request_id: UUID,
        *,
        event_type: ApprovalEventType,
        actor: str,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> ApprovalEvent: ...

    def list_events(
        self,
        project_id: UUID,
        *,
        approval_request_id: UUID | None = None,
    ) -> list[ApprovalEvent]: ...


class TraceabilityRepository(Protocol):
    def create_link(
        self,
        project_id: UUID,
        *,
        source_type: str,
        source_id: UUID,
        target_type: str,
        target_id: UUID,
        relationship_type: TraceabilityRelationshipType,
        metadata: dict | None = None,
    ) -> TraceabilityLink: ...

    def get_links_by_source(
        self,
        project_id: UUID,
        *,
        source_type: str,
        source_id: UUID,
    ) -> list[TraceabilityLink]: ...

    def get_links_by_target(
        self,
        project_id: UUID,
        *,
        target_type: str,
        target_id: UUID,
    ) -> list[TraceabilityLink]: ...

    def list_for_project(self, project_id: UUID) -> list[TraceabilityLink]: ...


class ReportRepository(Protocol):
    def create_report(
        self,
        project_id: UUID,
        *,
        report_type: ReportType,
        title: str,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> Report: ...

    def get_report(
        self,
        project_id: UUID,
        report_id: UUID,
    ) -> Report | None: ...

    def list_reports(
        self,
        project_id: UUID,
        *,
        report_type: ReportType | None = None,
    ) -> list[Report]: ...

    def update_report_status(
        self,
        project_id: UUID,
        report_id: UUID,
        *,
        status: ReportStatus,
        current_version: int | None = None,
    ) -> Report | None: ...

    def create_version(
        self,
        project_id: UUID,
        report_id: UUID,
        *,
        version: int,
        status: ReportVersionStatus,
        output_format: ReportOutputFormat,
        content: dict,
        traceability_metadata: dict,
        generated_by: str | None = None,
    ) -> ReportVersion: ...

    def get_version(
        self,
        project_id: UUID,
        report_id: UUID,
        version: int,
    ) -> ReportVersion | None: ...

    def get_latest_version(
        self,
        project_id: UUID,
        report_id: UUID,
    ) -> ReportVersion | None: ...

    def list_versions(
        self,
        project_id: UUID,
        report_id: UUID,
    ) -> list[ReportVersion]: ...


class AnalysisRepository(Protocol):
    def create_run(
        self,
        project_id: UUID,
        *,
        pem_snapshot_id: UUID,
        pem_version: int,
        analysis_type: str,
        status: AnalysisStatus,
        capability_status: str,
        message: str,
        inputs: dict | None = None,
        outputs: dict | None = None,
        model_summary: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> AnalysisRun: ...

    def update_run(
        self,
        project_id: UUID,
        run_id: UUID,
        *,
        status: AnalysisStatus,
        capability_status: str,
        message: str,
        outputs: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        completed_at: datetime | None = None,
    ) -> AnalysisRun | None: ...

    def get_run(self, project_id: UUID, run_id: UUID) -> AnalysisRun | None: ...

    def list_runs(
        self,
        project_id: UUID,
        *,
        limit: int = 50,
    ) -> list[AnalysisRun]: ...


class DesignRepository(Protocol):
    def create_run(
        self,
        project_id: UUID,
        *,
        pem_snapshot_id: UUID,
        pem_version: int,
        analysis_run_id: UUID | None,
        design_type: str,
        status: DesignStatus,
        capability_status: str,
        message: str,
        code_edition: str | None = None,
        inputs: dict | None = None,
        outputs: dict | None = None,
        model_summary: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> DesignRun: ...

    def update_run(
        self,
        project_id: UUID,
        run_id: UUID,
        *,
        status: DesignStatus,
        capability_status: str,
        message: str,
        outputs: dict | None = None,
        validation_summary: dict | None = None,
        metadata: dict | None = None,
        completed_at: datetime | None = None,
    ) -> DesignRun | None: ...

    def get_run(self, project_id: UUID, run_id: UUID) -> DesignRun | None: ...

    def list_runs(
        self,
        project_id: UUID,
        *,
        limit: int = 50,
    ) -> list[DesignRun]: ...


class OptimizationRepository(Protocol):
    def list_runs(
        self,
        project_id: UUID,
        *,
        limit: int = 50,
    ) -> list[OptimizationRun]: ...
