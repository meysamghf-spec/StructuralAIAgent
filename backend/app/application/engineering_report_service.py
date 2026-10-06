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
        return report


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
