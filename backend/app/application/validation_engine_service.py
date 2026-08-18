"""Independent ValidationEngine — input, code, and PEM consistency checks."""

from __future__ import annotations

from uuid import UUID

from app.application.code_engine_service import CodeEngineService
from app.application.exceptions import ProjectNotFoundError
from app.application.project_service import PemService, ProjectService
from app.domain.models.validation import (
    ValidationCategory,
    ValidationFinding,
    ValidationReport,
    ValidationStatus,
)


class ValidationEngineService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        code_engine_service: CodeEngineService,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._code_engine = code_engine_service

    def validate_project(self, project_id: UUID) -> ValidationReport:
        project = self._projects.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        pem = self._pem.get_current_pem(project_id)
        findings: list[ValidationFinding] = []

        if pem is None:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="MISSING_PEM",
                    message="Project engineering model is missing",
                )
            )
            return self._build_report(project_id, findings)

        code_result = self._code_engine.validate_configuration(pem.code_configuration)
        for conflict in code_result.conflicts:
            status = (
                ValidationStatus.ERROR
                if conflict.severity == "ERROR"
                else ValidationStatus.WARNING
            )
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.CODE,
                    status=status,
                    code=f"CODE_{conflict.conflict_type}",
                    message=conflict.message,
                    details={"affected_standards": conflict.affected_standards},
                )
            )

        for warning in code_result.warnings:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.CODE,
                    status=ValidationStatus.REQUIRES_ENGINEER_REVIEW,
                    code="CODE_SOFTWARE_DEFAULT",
                    message=warning,
                )
            )

        unit = pem.unit_configuration
        if not unit.length_unit or not unit.force_unit or not unit.stress_unit:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INCOMPLETE_UNIT_CONFIGURATION",
                    message="Unit configuration is incomplete",
                )
            )

        if not pem.metadata.name:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.WARNING,
                    code="MISSING_PROJECT_NAME",
                    message="PEM metadata name is empty",
                )
            )

        return self._build_report(project_id, findings)

    def _build_report(
        self, project_id: UUID, findings: list[ValidationFinding]
    ) -> ValidationReport:
        if not findings:
            overall = ValidationStatus.PASS
            summary = "All validation checks passed"
        elif any(f.status == ValidationStatus.ERROR for f in findings):
            overall = ValidationStatus.ERROR
            summary = "Validation failed with errors"
        elif any(f.status == ValidationStatus.REQUIRES_ENGINEER_REVIEW for f in findings):
            overall = ValidationStatus.REQUIRES_ENGINEER_REVIEW
            summary = "Validation requires engineer review"
        elif any(f.status == ValidationStatus.WARNING for f in findings):
            overall = ValidationStatus.WARNING
            summary = "Validation completed with warnings"
        else:
            overall = ValidationStatus.PASS
            summary = "All validation checks passed"

        return ValidationReport(
            project_id=project_id,
            overall_status=overall,
            findings=findings,
            summary=summary,
        )
