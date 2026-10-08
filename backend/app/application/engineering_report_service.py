"""Structured engineering report generated from the same PEM used for analysis and drawings."""

from __future__ import annotations

from typing import Any

from app.application.building_analysis_service import BuildingAnalysisResult
from app.application.preliminary_design_service import PreliminaryDesignResult
from app.domain.models.pem import ProjectEngineeringModel


class EngineeringReportService:
    def generate(
        self,
        pem: ProjectEngineeringModel,
        *,
        analysis: BuildingAnalysisResult | None = None,
        design: PreliminaryDesignResult | None = None,
        architectural_brief: dict[str, Any] | None = None,
        external_executions: list[dict[str, Any]] | None = None,
        learning: dict[str, Any] | None = None,
        drawings: dict[str, Any] | None = None,
        qa_package: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
        pem_version: int | None = None,
        coordination_warnings: list[dict[str, Any]] | None = None,
        design_checks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        structural = pem.structural_model
        building = pem.building_model
        site = building.site
        failed = [item for item in structural.design_checks if item.status.value == "FAIL"]
        warnings = [item for item in structural.design_checks if item.status.value == "WARNING"]
        report = {
            "title": "Preliminary automated engineering model",
            "disclaimer": (
                "Preliminary automated engineering model — requires review and approval "
                "by a qualified engineer."
            ),
            "lifecycle_status": pem.lifecycle_status,
            "code_compliance": pem.code_compliance
            or {
                "ACI 318-25": "PARTIAL_IMPLEMENTATION",
                "ASCE 7-22": "PARTIAL_IMPLEMENTATION",
                "AISC 360-22": "PARTIAL_IMPLEMENTATION",
                "IBC 2024": "PARTIAL_IMPLEMENTATION",
            },
            "1_project_information": {
                "name": pem.metadata.name,
                "project_id": str(pem.project_id),
                "units": pem.unit_configuration.system.value if pem.unit_configuration else "SI_METRIC",
            },
            "2_architectural_assumptions": {
                "frontage_m": site.frontage_m if site else None,
                "depth_m": site.depth_m if site else None,
                "floors": building.floor_count,
                "structural_system": building.structural_system.value,
            },
            "3_structural_system": pem.structural_system,
            "4_materials": {
                "concrete": [item.model_dump(mode="json") for item in structural.materials.concrete],
                "reinforcement": [item.model_dump(mode="json") for item in structural.materials.reinforcement],
            },
            "5_geometry": {
                "levels": [item.model_dump(mode="json") for item in structural.geometry.levels],
                "member_count": len(structural.members.members),
                "support_count": len(structural.supports),
            },
            "6_loads": [case.model_dump(mode="json") for case in structural.load_cases],
            "7_load_combinations": [item.model_dump(mode="json") for item in structural.load_combinations],
            "8_wind_assumptions": _cases_meta(structural, "WIND"),
            "9_seismic_assumptions": _cases_meta(structural, "SEISMIC"),
            "10_analysis_method": {
                "solver": (structural.analysis_model.configuration or {}).get("solver"),
                "status": analysis.status if analysis else (structural.analysis_model.configuration or {}).get("last_analysis_status"),
                "message": analysis.message if analysis else None,
                "assumptions": analysis.assumptions if analysis else [],
                "fidelity": "IMPLEMENTED_LINEAR_STATIC_3D"
                if "3d" in str((structural.analysis_model.configuration or {}).get("solver", "")).lower()
                else "IMPLEMENTED_LINEAR_STATIC_2D",
            },
            "11_story_drift": [item.model_dump(mode="json") for item in structural.story_drifts],
            "12_member_design": [item.model_dump(mode="json") for item in structural.design_checks[:200]],
            "13_reinforcement": [item.model_dump(mode="json") for item in structural.reinforcement[:200]],
            "14_foundation": [item.model_dump(mode="json") for item in structural.footings],
            "15_qa": pem.validation_results,
            "16_failures_warnings": {
                "fail_count": len(failed),
                "warning_count": len(warnings),
                "failed_checks": [item.model_dump(mode="json") for item in failed[:50]],
            },
            "17_design_iterations": pem.decisions,
            "18_approval_status": pem.lifecycle_status,
            "19_limitations": [
                "P-delta, cracked stiffness, live-load reduction and accidental torsion are not included.",
                "Wind and seismic procedures are simplified ASCE 7-22 implementations — see provenance.",
                "Member design is preliminary ACI 318-25 (no interaction diagrams, development lengths NOT_CHECKED).",
                "External solvers (ETABS/SAP2000/SAFE) remain required for final construction documents.",
            ],
            "input_provenance": [item.model_dump(mode="json") for item in structural.input_provenance],
            "authority": _authority(
                snapshot_id=snapshot_id,
                pem_version=pem_version,
                derived=_provenance(structural, "DERIVED"),
                assumed=_provenance(structural, "ASSUMED", "DEFAULT"),
                learning=learning,
                external_executions=external_executions,
            ),
            "architectural_brief": architectural_brief if architectural_brief is not None else (pem.requirements or {}).get("brief"),
            "derived_values": _provenance(structural, "DERIVED"),
            "assumed_values": _provenance(structural, "ASSUMED", "DEFAULT"),
            "analysis_software": {
                "internal": "preliminary linear-static analysis stored on the PEM",
                "ETABS": _software_status(external_executions, "ETABS"),
            },
            "analysis_execution_status": {
                "internal": report_analysis_status(analysis, structural),
                "ETABS": _software_status(external_executions, "ETABS"),
            },
            "design_software": {
                "internal": "existing preliminary and beam design checks",
                "ETABS": _software_status(external_executions, "ETABS"),
                "SAFE": _software_status(external_executions, "SAFE"),
            },
            "design_execution_status": {
                "internal_check_count": len(design_checks if design_checks is not None else structural.design_checks),
                "ETABS": _software_status(external_executions, "ETABS"),
                "SAFE": _software_status(external_executions, "SAFE"),
            },
            "learning_context": _learning(learning),
            "drawing_package": drawings,
            "external_software_executions": external_executions or _default_external(),
            "coordination_warnings": coordination_warnings or [],
            "final_engineering_readiness": {
                "status": (qa_package or {}).get("status", "NOT_RUN"),
                "final_engineering_approval": False,
                "statement": "Learning context did not produce or approve an engineering result.",
            },
            "classification": {
                "IMPLEMENTED": [
                    "3D direct-stiffness frame analysis",
                    "Rigid diaphragms",
                    "Gravity tributary loads (ASCE 7-22 live-load tables)",
                    "Simplified directional MWFRS wind walls",
                    "ELF seismic storey forces",
                    "Elastic storey drift",
                    "Preliminary ACI beam/column/slab/footing checks",
                    "Structured reinforcement",
                ],
                "PRELIMINARY": [
                    "Wind (walls only)",
                    "ELF seismic (assumed Ss/S1 unless supplied)",
                    "Foundation bearing",
                    "Slab one-way strip",
                ],
                "NOT_CHECKED": [
                    "Modal analysis",
                    "Accidental torsion",
                    "Weak storey strength",
                    "Torsional irregularity δmax/δavg",
                    "Development length / cutoffs",
                    "Two-way slab FEM",
                ],
                "REQUIRES_ENGINEER_REVIEW": True,
            },
        }
        report["15_learning_context"] = report["learning_context"]
        report["16_pem_provenance"] = report["authority"]["AUTHORITATIVE ENGINEERING INPUT"]
        report["18_external_software_execution_records"] = report["external_software_executions"]
        report["19_warnings"] = report["coordination_warnings"]
        report["20_final_engineering_readiness"] = report["final_engineering_readiness"]
        return report


def report_analysis_status(analysis: BuildingAnalysisResult | None, structural) -> dict[str, Any]:
    configuration = structural.analysis_model.configuration or {}
    return {
        "solver": configuration.get("solver"),
        "status": analysis.status if analysis else configuration.get("last_analysis_status"),
        "executed": (analysis.status if analysis else configuration.get("last_analysis_status")) == "SUCCESS",
        "label": "INTERNAL",
    }


def _provenance(structural, *origins: str) -> list[dict[str, Any]]:
    items = []
    for item in structural.input_provenance:
        if item.origin.value in origins:
            items.append(
                {
                    "field": item.field,
                    "value": item.value,
                    "origin": item.origin.value,
                    "note": item.note,
                }
            )
    return items


def _learning(learning: dict[str, Any] | None) -> dict[str, Any]:
    record_ids = []
    if isinstance(learning, dict) and isinstance(learning.get("record_ids"), list):
        record_ids = [str(item) for item in learning["record_ids"]]
    return {
        "heading": "LEARNING CONTEXT",
        "authority": "CONTEXT_ONLY",
        "record_ids": record_ids,
        "used": bool(record_ids),
        "produced_engineering_result": False,
        "approved_engineering_result": False,
        "overrides_pem": False,
        "overrides_calculations": False,
        "overrides_qa": False,
        "statement": "Approved learning is context only. It did not produce or approve an engineering result.",
    }


def _default_external() -> list[dict[str, Any]]:
    return [
        {
            "software": name,
            "executed": False,
            "status": "NOT_EXECUTED",
            "errors": [f"{name} was not invoked for this report."],
            "provenance": {"source": "engineering_report"},
        }
        for name in ("ETABS", "SAFE", "AUTOCAD")
    ]


def _software_status(executions: list[dict[str, Any]] | None, software: str) -> dict[str, Any]:
    for item in executions or []:
        if item.get("software") == software:
            return {
                "executed": item.get("executed") is True,
                "status": item.get("status") or "NOT_EXECUTED",
            }
    return {"executed": False, "status": "NOT_EXECUTED"}


def _authority(
    *,
    snapshot_id: str | None,
    pem_version: int | None,
    derived: list[dict[str, Any]],
    assumed: list[dict[str, Any]],
    learning: dict[str, Any] | None,
    external_executions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    return {
        "AUTHORITATIVE ENGINEERING INPUT": {
            "heading": "AUTHORITATIVE ENGINEERING INPUT",
            "source": "current PEM snapshot",
            "pem_version": pem_version,
            "pem_snapshot_id": snapshot_id,
        },
        "DERIVED": derived,
        "ASSUMED": assumed,
        "LEARNING CONTEXT": _learning(learning),
        "EXTERNAL SOFTWARE RESULT": external_executions or _default_external(),
    }


def _cases_meta(structural, category: str) -> dict[str, Any]:
    cases = [case for case in structural.load_cases if case.category.value == category]
    if not cases:
        return {"status": "NOT_IMPLEMENTED"}
    first = cases[0]
    return {
        "status": (first.metadata or {}).get("fidelity", "PRELIMINARY"),
        "code_reference": first.code_reference,
        "case_names": [case.name for case in cases],
        "metadata": first.metadata,
    }
