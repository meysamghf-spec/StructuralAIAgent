"""Engineering report generation service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.application.exceptions import ProjectNotFoundError, ReportNotFoundError
from app.application.engineering_result_service import EngineeringResultService
from app.application.human_approval_service import HumanApprovalService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.traceability_service import TraceabilityService
from app.application.validation_engine_service import ValidationEngineService
from app.application.project_service import PemService
from app.domain.models.human_approval import ApprovalStatus
from app.domain.models.project_memory import MemoryType
from app.domain.models.reporting import (
    GeneratedReportData,
    Report,
    ReportGenerationRequest,
    ReportOutputFormat,
    ReportSection,
    ReportStatus,
    ReportType,
    ReportVersion,
    ReportVersionStatus,
)
from app.domain.models.traceability import TraceObjectType, TraceabilityRelationshipType
from app.domain.report_templates import get_report_template
from app.domain.repositories.protocols import (
    AnalysisRepository,
    DesignRepository,
    OptimizationRepository,
    ProjectRepository,
    ReportRepository,
)


class ReportGenerationService:
    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        report_repository: ReportRepository,
        context_service: ProjectContextAssemblyService,
        traceability_service: TraceabilityService,
        approval_service: HumanApprovalService,
        validation_service: ValidationEngineService,
        pem_service: PemService,
        analysis_repository: AnalysisRepository | None = None,
        design_repository: DesignRepository | None = None,
        optimization_repository: OptimizationRepository | None = None,
        engineering_result_service: EngineeringResultService | None = None,
    ) -> None:
        self._projects = project_repository
        self._reports = report_repository
        self._context = context_service
        self._traceability = traceability_service
        self._approvals = approval_service
        self._validation = validation_service
        self._pem = pem_service
        self._analysis = analysis_repository
        self._design = design_repository
        self._optimization = optimization_repository
        self._engineering_results = engineering_result_service

    def create_report(
        self,
        project_id: UUID,
        *,
        report_type: ReportType,
        title: str | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> Report:
        self._ensure_project_exists(project_id)
        template = get_report_template(report_type)
        return self._reports.create_report(
            project_id,
            report_type=report_type,
            title=title or template.title,
            metadata=metadata,
            created_by=created_by,
        )

    def list_reports(
        self,
        project_id: UUID,
        *,
        report_type: ReportType | None = None,
    ) -> list[Report]:
        self._ensure_project_exists(project_id)
        return self._reports.list_reports(project_id, report_type=report_type)

    def get_report(self, project_id: UUID, report_id: UUID) -> Report:
        self._ensure_project_exists(project_id)
        report = self._reports.get_report(project_id, report_id)
        if report is None:
            raise ReportNotFoundError(project_id, report_id)
        return report

    def get_report_version(
        self,
        project_id: UUID,
        report_id: UUID,
        version: int,
    ) -> ReportVersion:
        self._ensure_project_exists(project_id)
        report_version = self._reports.get_version(project_id, report_id, version)
        if report_version is None:
            raise ReportNotFoundError(project_id, report_id, version=version)
        return report_version

    def generate_version(self, request: ReportGenerationRequest) -> ReportVersion:
        report = self.get_report(request.project_id, request.report_id)
        if report.report_type != request.report_type:
            request = request.model_copy(update={"report_type": report.report_type})

        self._reports.update_report_status(
            request.project_id,
            request.report_id,
            status=ReportStatus.GENERATING,
        )

        generated = self._assemble_report_data(request)
        next_version = report.current_version + 1
        traceability_metadata = generated.traceability_metadata

        version = self._reports.create_version(
            request.project_id,
            request.report_id,
            version=next_version,
            status=ReportVersionStatus.COMPLETED,
            output_format=request.output_format,
            content=generated.model_dump(mode="json"),
            traceability_metadata=traceability_metadata,
            generated_by=request.requested_by,
        )

        self._reports.update_report_status(
            request.project_id,
            request.report_id,
            status=ReportStatus.COMPLETED,
            current_version=next_version,
        )

        self._attach_report_to_traceability(
            request.project_id,
            report_id=report.id,
            version=version,
            graph=generated.traceability_metadata.get("graph", {}),
        )

        return version

    def _attach_report_to_traceability(
        self,
        project_id: UUID,
        *,
        report_id: UUID,
        version: ReportVersion,
        graph: dict[str, Any],
    ) -> None:
        links = graph.get("links", [])
        if links:
            last = links[-1]
            source_type = last.get("target_type", TraceObjectType.REPORT.value)
            source_id = UUID(str(last.get("target_id")))
        else:
            source_type = TraceObjectType.REPORT.value
            source_id = report_id

        self._traceability.create_link(
            project_id,
            source_type=source_type,
            source_id=source_id,
            target_type=TraceObjectType.REPORT.value,
            target_id=version.id,
            relationship_type=TraceabilityRelationshipType.DESIGN_TO_REPORT,
            metadata={"report_id": str(report_id), "version": version.version},
        )

    def get_report_traceability(
        self,
        project_id: UUID,
        report_id: UUID,
    ) -> dict[str, Any]:
        report = self.get_report(project_id, report_id)
        latest = self._reports.get_latest_version(project_id, report_id)
        graph = self._traceability.get_project_graph(project_id)

        chain = self._build_traceability_chain_summary(graph.model_dump(mode="json"))
        if latest is not None:
            stored_chain = latest.traceability_metadata.get("chain_summary")
            if stored_chain:
                chain = stored_chain

        return {
            "report_id": str(report.id),
            "report_type": report.report_type.value,
            "current_version": report.current_version,
            "chain_summary": chain,
            "graph": graph.model_dump(mode="json"),
            "latest_version_traceability": (
                latest.traceability_metadata if latest is not None else {}
            ),
        }

    def _assemble_report_data(self, request: ReportGenerationRequest) -> GeneratedReportData:
        context = self._context.assemble(request.project_id)
        graph = self._traceability.get_project_graph(request.project_id)
        approvals = self._approvals.list_requests(request.project_id)
        validation = self._validation.validate_project(request.project_id)

        pem = self._pem.get_current_pem(request.project_id)

        traceability_metadata = {
            "graph": graph.model_dump(mode="json"),
            "chain_summary": self._build_traceability_chain_summary(
                graph.model_dump(mode="json")
            ),
            "validation_status": validation.overall_status.value,
        }

        sections = self._build_sections(
            request.report_type,
            context=context.model_dump(mode="json"),
            graph=graph.model_dump(mode="json"),
            approvals=[item.model_dump(mode="json") for item in approvals],
            validation=validation.model_dump(mode="json"),
            pem=pem.model_dump(mode="json") if pem is not None else None,
            analysis_runs=self._list_analysis_runs(request.project_id),
            design_runs=self._list_design_runs(request.project_id),
            optimization_runs=self._list_optimization_runs(request.project_id),
        )

        return GeneratedReportData(
            report_type=request.report_type,
            project_id=request.project_id,
            project_name=context.project_name,
            generated_at=datetime.now(UTC),
            sections=sections,
            traceability_metadata=traceability_metadata,
        )

    def _build_sections(
        self,
        report_type: ReportType,
        *,
        context: dict[str, Any],
        graph: dict[str, Any],
        approvals: list[dict[str, Any]],
        validation: dict[str, Any],
        pem: dict[str, Any] | None,
        analysis_runs: list[dict[str, Any]] | None = None,
        design_runs: list[dict[str, Any]] | None = None,
        optimization_runs: list[dict[str, Any]] | None = None,
    ) -> list[ReportSection]:
        template = get_report_template(report_type)
        sections: list[ReportSection] = []

        for key in template.section_keys:
            if key == "project_information":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Project Information",
                        content={
                            "project_id": context["project_id"],
                            "project_name": context["project_name"],
                            "pem_version": context.get("pem_version"),
                        },
                    )
                )
            elif key == "configuration":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Configuration",
                        content={
                            "code_configuration": context.get("code_configuration"),
                            "unit_configuration": context.get("unit_configuration"),
                        },
                    )
                )
            elif key == "code_configuration":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Code Configuration",
                        content={"code_configuration": context.get("code_configuration")},
                    )
                )
            elif key == "engineering_model":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Engineering Model",
                        content={
                            "pem_version": context.get("pem_version"),
                            "unit_configuration": context.get("unit_configuration"),
                            "analysis_models": pem.get("analysis_models", []) if pem else [],
                            "design_results": pem.get("design_results", []) if pem else [],
                        },
                    )
                )
            elif key == "project_memory":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Project Memory",
                        content={
                            "memory_total_count": context.get("memory_total_count"),
                            "memory_counts_by_type": context.get("memory_counts_by_type"),
                            "memories": context.get("memories", []),
                        },
                    )
                )
            elif key == "files":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Project Files",
                        content={"files": context.get("files", [])},
                    )
                )
            elif key == "decisions":
                memories = context.get("memories", [])
                sections.append(
                    ReportSection(
                        key=key,
                        title="Decisions",
                        content={
                            "decisions": [
                                item
                                for item in memories
                                if item.get("memory_type")
                                in {MemoryType.DECISION.value, MemoryType.REJECTION.value}
                            ]
                        },
                    )
                )
            elif key == "approvals":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Approvals",
                        content={
                            "pending": [
                                item for item in approvals if item.get("status") == ApprovalStatus.PENDING.value
                            ],
                            "resolved": [
                                item
                                for item in approvals
                                if item.get("status") != ApprovalStatus.PENDING.value
                            ],
                        },
                    )
                )
            elif key == "analysis_results":
                engineering_results = self._list_engineering_results(request.project_id)
                sections.append(
                    ReportSection(
                        key=key,
                        title="Analysis Results",
                        content={
                            "analysis_runs": analysis_runs or [],
                            "validated_engineering_results": engineering_results,
                            "real_solver_results_available": any(
                                item.get("engineering_results_available") for item in engineering_results
                            ),
                            "legacy_pem_analysis_models": pem.get("analysis_models", []) if pem else [],
                            "solver_unavailable_message": (
                                None
                                if any(item.get("engineering_results_available") for item in engineering_results)
                                else "Real solver results are not available"
                            ),
                        },
                    )
                )
            elif key == "design_results":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Design Results",
                        content={
                            "design_runs": design_runs or [],
                            "legacy_pem_design_results": pem.get("design_results", []) if pem else [],
                        },
                    )
                )
            elif key == "optimization_results":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Optimization Results",
                        content={
                            "optimization_runs": optimization_runs or [],
                        },
                    )
                )
            elif key == "validation_results":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Validation Results",
                        content=validation,
                    )
                )
            elif key == "traceability_chain":
                sections.append(
                    ReportSection(
                        key=key,
                        title="Traceability Chain",
                        content={
                            "chain_summary": self._build_traceability_chain_summary(graph),
                            "links": graph.get("links", []),
                        },
                    )
                )

        return sections

    @staticmethod
    def _build_traceability_chain_summary(graph: dict[str, Any]) -> list[str]:
        ordered = [
            TraceabilityRelationshipType.REQUIREMENT_TO_SOURCE.value,
            TraceabilityRelationshipType.SOURCE_TO_MEMORY.value,
            TraceabilityRelationshipType.MEMORY_TO_DECISION.value,
            TraceabilityRelationshipType.DECISION_TO_APPROVAL.value,
            TraceabilityRelationshipType.APPROVAL_TO_MODEL.value,
            TraceabilityRelationshipType.MODEL_TO_ANALYSIS.value,
            TraceabilityRelationshipType.ANALYSIS_TO_DESIGN.value,
            TraceabilityRelationshipType.DESIGN_TO_OPTIMIZATION.value,
            TraceabilityRelationshipType.ANALYSIS_TO_OPTIMIZATION.value,
            TraceabilityRelationshipType.MODEL_TO_OPTIMIZATION.value,
            TraceabilityRelationshipType.OPTIMIZATION_TO_REPORT.value,
            TraceabilityRelationshipType.DESIGN_TO_REPORT.value,
        ]
        present = {link.get("relationship_type") for link in graph.get("links", [])}
        summary = [step for step in ordered if step in present]
        validation_present = any(
            link.get("target_type") == TraceObjectType.REPORT.value for link in graph.get("links", [])
        )
        if validation_present and "VALIDATION_TO_REPORT" not in summary:
            summary.append("VALIDATION_TO_REPORT")
        summary.append("REPORT")
        return summary

    def _list_engineering_results(self, project_id: UUID) -> list[dict[str, Any]]:
        if self._engineering_results is None:
            return []
        return [
            item.model_dump(mode="json")
            for item in self._engineering_results.list_result_sets(project_id, limit=20)
        ]

    def _list_analysis_runs(self, project_id: UUID) -> list[dict[str, Any]]:
        if self._analysis is None:
            return []
        runs = self._analysis.list_runs(project_id, limit=20)
        return [run.model_dump(mode="json") for run in runs]

    def _list_design_runs(self, project_id: UUID) -> list[dict[str, Any]]:
        if self._design is None:
            return []
        runs = self._design.list_runs(project_id, limit=20)
        return [run.model_dump(mode="json") for run in runs]

    def _list_optimization_runs(self, project_id: UUID) -> list[dict[str, Any]]:
        if self._optimization is None:
            return []
        runs = self._optimization.list_runs(project_id, limit=20)
        return [run.model_dump(mode="json") for run in runs]

    def _ensure_project_exists(self, project_id: UUID) -> None:
        if self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id)
