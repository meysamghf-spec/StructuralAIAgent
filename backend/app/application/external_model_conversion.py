"""Convert ProjectEngineeringModel structural data to/from external solver payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.models.integration import (
    ExternalAnalysisResults,
    ExternalModelExport,
    IntegrationSoftware,
)
from app.domain.models.pem import ProjectEngineeringModel


SUPPORTED_RESULT_TYPES = frozenset(
    {
        "reactions",
        "member_forces",
        "joint_displacements",
        "story_drifts",
        "modal_periods",
        "load_combination_results",
        "shell_results",
    }
)


def build_external_model_export(
    *,
    project_id: UUID,
    pem: ProjectEngineeringModel,
    pem_snapshot_id: UUID,
    pem_version: int,
    software: IntegrationSoftware,
    software_version: str,
    metadata: dict[str, Any] | None = None,
) -> ExternalModelExport:
    structural = pem.structural_model
    return ExternalModelExport(
        project_id=project_id,
        pem_snapshot_id=pem_snapshot_id,
        pem_version=pem_version,
        software=software,
        software_version=software_version,
        exported_at=datetime.now(UTC),
        structural_model={
            "geometry": structural.geometry.model_dump(mode="json"),
            "materials": structural.materials.model_dump(mode="json"),
            "sections": structural.sections.model_dump(mode="json"),
            "members": structural.members.model_dump(mode="json"),
            "supports": [item.model_dump(mode="json") for item in structural.supports],
            "load_cases": [item.model_dump(mode="json") for item in structural.load_cases],
            "load_combinations": [
                item.model_dump(mode="json") for item in structural.load_combinations
            ],
            "analysis_model": structural.analysis_model.model_dump(mode="json"),
            "design_parameters": structural.design_parameters.model_dump(mode="json"),
        },
        metadata={
            "code_configuration": pem.code_configuration.model_dump(mode="json"),
            "unit_configuration": pem.unit_configuration.model_dump(mode="json"),
            **(metadata or {}),
        },
    )


def validate_external_model_export(export: ExternalModelExport) -> tuple[bool, list[str]]:
    issues: list[str] = []
    members = export.structural_model.get("members", {}).get("members", [])
    if not members:
        issues.append("At least one structural member is required for export")
    load_cases = export.structural_model.get("load_cases", [])
    if not load_cases:
        issues.append("At least one load case is recommended before export")
    return len(issues) == 0, issues


def parse_external_analysis_results(
    *,
    software: IntegrationSoftware,
    software_version: str,
    project_id: UUID,
    pem_snapshot_id: UUID,
    pem_version: int,
    raw_results: dict[str, Any],
    analysis_run_id: UUID | None = None,
) -> ExternalAnalysisResults:
    present_types = [
        key
        for key in SUPPORTED_RESULT_TYPES
        if key in raw_results and raw_results[key] not in (None, [], {})
    ]
    return ExternalAnalysisResults(
        software=software,
        software_version=software_version,
        project_id=project_id,
        pem_snapshot_id=pem_snapshot_id,
        pem_version=pem_version,
        analysis_run_id=analysis_run_id,
        imported_at=datetime.now(UTC),
        result_types_present=present_types,
        results={key: raw_results[key] for key in present_types},
        provenance={
            "source_software": software.value,
            "source_version": software_version,
            "import_timestamp": datetime.now(UTC).isoformat(),
            "external_model_identity": raw_results.get("external_model_identity"),
            "execution_mode": raw_results.get("execution_mode", "vendor"),
        },
    )


def validate_imported_results(results: ExternalAnalysisResults) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not results.result_types_present:
        issues.append("No supported engineering result types were returned by the external software")
    if results.provenance.get("execution_mode") == "mock":
        issues.append("Mock execution results cannot be validated as engineering outputs")
    return len(issues) == 0, issues
