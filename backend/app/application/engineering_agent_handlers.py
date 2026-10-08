"""Engineering agent handlers — delegate to deterministic platform services."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from app.application.agent_output_helpers import (
    analysis_user_summary,
    capability_label,
    design_user_summary,
    optimization_user_summary,
    validation_label,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentResult
from app.domain.models.analysis import AnalysisRequest
from app.domain.models.design import DesignRequest
from app.domain.models.optimization import OptimizationRequest
from app.domain.models.cad import CadDrawingRequest, CadOutputFormat
from app.application.aci_rc_beam_check import is_aci_rc_beam_check_request, run_aci_rc_beam_check
from app.application.aisc_steel_beam_check import is_aisc_steel_beam_check_request, run_aisc_steel_beam_check
from app.application.building_brief_parser import BuildingBriefParser
from app.application.demo_rc_beam_analysis import analyze_simply_supported_rc_beam
from app.application.engineering_agent_services import EngineeringAgentServices
from app.domain.models.reporting import ReportGenerationRequest, ReportType


class EngineeringAgentHandler(Protocol):
    agent_type: EngineeringAgentType

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult: ...


def _project_id(context: dict[str, Any]) -> UUID:
    return UUID(str(context["project_id"]))


def _context_summary(context: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "project_id": context.get("project_id"),
        "project_name": context.get("project_name"),
        "pem_version": context.get("pem_version"),
        "memory_total_count": context.get("memory_total_count"),
        "file_count": len(context.get("files", [])),
        "code_configuration": context.get("code_configuration"),
        "unit_configuration": context.get("unit_configuration"),
    }
    record_ids = context.get("learning_record_ids")
    if isinstance(record_ids, list) and record_ids:
        summary["approved_learning_count"] = len(record_ids)
        summary["learning_explanation"] = context.get("learning_explanation")
        summary["learning_record_ids"] = list(record_ids)
        summary["learning_authority"] = context.get("learning_authority", "CONTEXT_ONLY")
        experience = context.get("approved_engineering_experience")
        if isinstance(experience, dict) and experience.get("heading"):
            summary["approved_engineering_experience_heading"] = experience["heading"]
    return summary


def _base_output(
    *,
    agent_type: EngineeringAgentType,
    action: str,
    user_request: str,
    parameters: dict[str, Any],
    context: dict[str, Any],
    capability_status: str,
    status_message: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = {
        "agent_type": agent_type.value,
        "action": action,
        "capability_status": capability_status,
        "status_message": status_message,
        "user_request": user_request,
        "parameters": parameters,
        "context_summary": _context_summary(context),
    }
    if payload:
        output.update(payload)
    return output


def _looks_like_building_brief(user_request: str, parameters: dict[str, Any]) -> bool:
    if parameters.get("generate_building") is True:
        return True
    brief = BuildingBriefParser().parse(user_request)
    if brief.has_plot_geometry:
        return True
    lowered = user_request.lower()
    markers = (
        "building layout",
        "design this building",
        "design the building",
        "residential floors",
        "parking spaces",
        "پیلوت",
        "طبقه مسکونی",
        "این ساختمان",
        "ساختمان را طراحی",
        "طراحی کن",
        "پارکینگ",
        "زمین",
    )
    return any(marker in user_request or marker in lowered for marker in markers)


def _demo_rc_beam_result(
    *,
    agent_type: EngineeringAgentType,
    action: str,
    user_request: str,
    parameters: dict[str, Any],
    context: dict[str, Any],
) -> AgentResult | None:
    demo = analyze_simply_supported_rc_beam(user_request)
    if demo is None:
        return None
    payload = demo.to_dict()
    payload["project_context_used"] = _context_summary(context)
    return AgentResult(
        structured_output=_base_output(
            agent_type=agent_type,
            action=action,
            user_request=user_request,
            parameters=parameters,
            context=context,
            capability_status="DEMO_COMPLETED",
            status_message=demo.to_markdown(),
            payload={
                "demo_rc_beam": payload,
                "user_summary": demo.to_markdown(),
            },
        ),
        confidence=1.0,
        generated_artifacts=[
            {
                "type": "demo_calculation",
                "name": "RC beam Demo analysis",
                "description": "Deterministic simply-supported UDL beam Demo (not a CSI/CAD run).",
            }
        ],
        recommendations=[
            "Treat this as a demonstration of chat-to-calculation flow, not a construction document.",
            "Next: attach a drawing or specification, then request validation against the project code profile.",
        ],
        validation_information={
            "capability_status": "DEMO_COMPLETED",
            "demo": True,
            "requires_approval": False,
            "warnings": list(demo.warnings),
        },
    )


def _aci_rc_beam_result(
    *,
    agent_type: EngineeringAgentType,
    action: str,
    user_request: str,
    parameters: dict[str, Any],
    context: dict[str, Any],
    services: EngineeringAgentServices,
    require_explicit_concrete: bool = False,
) -> AgentResult | None:
    if not is_aci_rc_beam_check_request(
        user_request, require_explicit_concrete=require_explicit_concrete
    ):
        return None
    outcome = run_aci_rc_beam_check(
        user_request=user_request,
        parameters=parameters,
        context=context,
        code_engine=services.code_engine,
    )
    if outcome is None:
        return None

    payload = dict(outcome.payload)
    warnings = list(payload.get("warnings") or [])
    if context.get("files"):
        warning = (
            "Attached project files were not used as numerical inputs. "
            "This check does not parse ETABS, SAP2000, SAFE, DWG, or PDF for member demands yet."
        )
        if warning not in warnings:
            warnings.append(warning)
        payload["warnings"] = warnings

    completed = outcome.status in {"PASS", "FAIL"}
    artifacts = []
    if completed:
        artifacts.append(
            {
                "type": "code_check",
                "name": "ACI 318 RC beam check",
                "description": "Deterministic ACI 318-25 flexure and concrete-shear check (no CSI/CAD).",
            }
        )
    recommendations = [
        "Independent engineer review is required before using these values in construction documents.",
    ]
    if outcome.status == "MISSING_REQUIRED_INPUT":
        recommendations = [
            "Provide the listed inputs. The agent will not invent span, section, materials, As, or demands.",
        ]
    elif outcome.status == "UNSUPPORTED_CODE":
        recommendations = [
            "Configure the project concrete code to ACI CODE-318-25, or wait for an implemented plugin.",
        ]
    elif outcome.status == "INVALID_INPUT":
        recommendations = [
            "Correct the out-of-range values and resubmit the check.",
        ]

    return AgentResult(
        structured_output=_base_output(
            agent_type=agent_type,
            action=action,
            user_request=user_request,
            parameters=parameters,
            context=context,
            capability_status=outcome.status,
            status_message=outcome.message,
            payload={
                "aci_rc_beam": payload,
                "user_summary": outcome.message,
            },
        ),
        confidence=1.0,
        generated_artifacts=artifacts,
        recommendations=recommendations,
            validation_information={
                "capability_status": outcome.status,
                "validation_status": outcome.validation_status,
                "requires_approval": outcome.requires_approval,
                "warnings": warnings,
            },
        )


def _aisc_steel_beam_result(
    *,
    agent_type: EngineeringAgentType,
    action: str,
    user_request: str,
    parameters: dict[str, Any],
    context: dict[str, Any],
    services: EngineeringAgentServices,
) -> AgentResult | None:
    if not is_aisc_steel_beam_check_request(user_request):
        return None
    outcome = run_aisc_steel_beam_check(
        user_request=user_request,
        parameters=parameters,
        context=context,
        code_engine=services.code_engine,
    )
    if outcome is None:
        return None

    payload = dict(outcome.payload)
    warnings = list(payload.get("warnings") or [])
    if context.get("files"):
        warning = (
            "Attached project files were not used as numerical inputs. "
            "This check does not parse ETABS, SAP2000, SAFE, DWG, or PDF for member demands yet."
        )
        if warning not in warnings:
            warnings.append(warning)
        payload["warnings"] = warnings

    completed = outcome.status in {"PASS", "FAIL"}
    artifacts = []
    if completed:
        artifacts.append(
            {
                "type": "code_check",
                "name": "AISC 360 steel beam flexure check",
                "description": "Deterministic AISC 360-22 compact plastic-moment flexure check (no CSI/CAD).",
            }
        )
    recommendations = [
        "Independent engineer review is required before using these values in construction documents.",
    ]
    if outcome.status == "MISSING_REQUIRED_INPUT":
        recommendations = [
            "Provide Fy, Zx, and Mu (or span and uniform load). The agent will not invent steel properties or demands.",
        ]
    elif outcome.status == "UNSUPPORTED_CODE":
        recommendations = [
            "Configure the project steel code to AISC 360-22, or wait for an implemented plugin.",
        ]
    elif outcome.status == "INVALID_INPUT":
        recommendations = [
            "Correct the out-of-range values and resubmit the check.",
        ]

    return AgentResult(
        structured_output=_base_output(
            agent_type=agent_type,
            action=action,
            user_request=user_request,
            parameters=parameters,
            context=context,
            capability_status=outcome.status,
            status_message=outcome.message,
            payload={
                "aisc_steel_beam": payload,
                "user_summary": outcome.message,
            },
        ),
        confidence=1.0,
        generated_artifacts=artifacts,
        recommendations=recommendations,
        validation_information={
            "capability_status": outcome.status,
            "validation_status": outcome.validation_status,
            "requires_approval": outcome.requires_approval,
            "warnings": warnings,
        },
    )


class StructuralModelingAgentHandler:
    agent_type = EngineeringAgentType.STRUCTURAL_MODELING_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        if _looks_like_building_brief(user_request, parameters):
            return self._generate_building(user_request=user_request, parameters=parameters, context=context)

        pem_version = context.get("pem_version")
        missing: list[str] = []
        if pem_version in (None, 0):
            missing.append("Engineering model baseline")
        if context.get("code_configuration") is None:
            missing.append("Code configuration")
        if context.get("unit_configuration") is None:
            missing.append("Unit system")

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="structural_modeling",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status="READY_FOR_MODELING_WORKFLOW",
                status_message="Modeling workflow prepared using current project context.",
                payload={
                    "pem_version": pem_version,
                    "missing_inputs": missing,
                    "next_steps": [
                        "Confirm geometry and system layout inputs",
                        "Apply approved material and section assumptions",
                    ],
                },
            ),
            confidence=0.4 if not missing else 0.2,
            recommendations=[
                "Review missing inputs before applying model changes.",
            ]
            if missing
            else ["Proceed with geometry updates aligned to project requirements."],
            validation_information={
                "capability_status": "READY_FOR_MODELING_WORKFLOW",
                "requires_approval": True,
            },
        )

    def _generate_building(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        pipeline = self._services.building_design_pipeline
        if pipeline is None:
            return AgentResult(
                structured_output=_base_output(
                    agent_type=self.agent_type,
                    action="building_generation",
                    user_request=user_request,
                    parameters=parameters,
                    context=context,
                    capability_status="NOT_CONFIGURED",
                    status_message="Building design pipeline is not configured.",
                ),
                confidence=0.0,
                recommendations=["Use the Model workspace Generate building action once the pipeline is wired."],
                validation_information={"capability_status": "NOT_CONFIGURED"},
            )

        result = pipeline.generate_from_brief(
            _project_id(context),
            user_request,
            created_by=str(context.get("actor_id") or "building-agent"),
            max_iterations=int(parameters.get("max_iterations") or 5),
            generate_drawings=bool(parameters.get("generate_drawings", True)),
        )
        waiting = result.assembled.status == "WAITING_FOR_INPUT"
        capability = "WAITING_FOR_INPUT" if waiting else result.assembled.status
        message = (
            "Missing critical inputs: " + "; ".join(result.assembled.missing_inputs)
            if waiting
            else (
                "Generated a preliminary architectural and structural model from the brief. "
                "Results are automated/preliminary and require engineer review before use."
            )
        )
        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="building_generation",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=capability,
                status_message=message,
                payload={
                    "summary": result.summary,
                    "pem_version": result.pem_version,
                    "snapshot_id": str(result.snapshot_id) if result.snapshot_id else None,
                    "approval_request_id": str(result.approval_request_id)
                    if result.approval_request_id
                    else None,
                    "drawing_ids": result.drawing_ids,
                    "sheet_paths": result.sheet_paths,
                    "missing_inputs": result.assembled.missing_inputs,
                    "fidelity": result.summary.get("fidelity"),
                },
            ),
            confidence=0.2 if waiting else 0.7,
            recommendations=(
                [f"Provide: {item}" for item in result.assembled.missing_inputs]
                if waiting
                else [
                    "Review generated geometry, analysis and design in the Model workspace.",
                    "Approve or reject the pending model-change request before treating the model as issued.",
                    "Wind and seismic intensities are PRELIMINARY_NOT_CODE placeholders.",
                ]
            ),
            validation_information={
                "capability_status": capability,
                "qa_status": result.assembled.qa.overall_status,
                "requires_approval": True,
                "failed_members": result.assembled.design.failed_member_ids,
            },
        )


class LoadAssessmentAgentHandler:
    agent_type = EngineeringAgentType.LOAD_ASSESSMENT_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        project_id = _project_id(context)
        load_summary: dict[str, Any] | None = None
        capability_status = "READY_FOR_LOAD_REVIEW"
        message = "Load assessment prepared from project code and model context."

        try:
            load_summary = self._services.analysis_engine.summarize_load_combinations(project_id)
        except Exception:
            capability_status = "MISSING_MODEL"
            message = "Load combinations require an initialized engineering model."

        code_configuration = context.get("code_configuration")
        loading_standard = None
        if isinstance(code_configuration, dict):
            loading_standard = code_configuration.get("loading_standard")

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="load_assessment",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=capability_status,
                status_message=message,
                payload={
                    "loading_standard": loading_standard,
                    "load_combinations": load_summary,
                },
            ),
            confidence=0.5 if load_summary else 0.25,
            recommendations=[
                "Confirm occupancy assumptions and environmental loads with the project team.",
            ],
            validation_information={"capability_status": capability_status},
        )


class AnalysisAgentHandler:
    agent_type = EngineeringAgentType.ANALYSIS_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        demo = _demo_rc_beam_result(
            agent_type=self.agent_type,
            action="analysis",
            user_request=user_request,
            parameters=parameters,
            context=context,
        )
        if demo is not None:
            return demo
        analysis_type = str(parameters.get("analysis_type", "LATERAL_DRIFT"))
        analysis_parameters = dict(parameters.get("analysis_parameters", {}))
        for key in ("solver", "software"):
            if parameters.get(key) and key not in analysis_parameters:
                analysis_parameters[key] = parameters[key]
        result = self._services.analysis_engine.run_analysis(
            AnalysisRequest(
                project_id=_project_id(context),
                analysis_type=analysis_type,
                parameters=analysis_parameters,
            )
        )

        result_set_id = result.outputs.get("result_set_id")
        validation_status = result.outputs.get("result_validation_status")
        user_summary = analysis_user_summary(
            capability_status=result.capability_status,
            message=result.message,
            result_set_id=str(result_set_id) if result_set_id else None,
            validation_status=str(validation_status) if validation_status else None,
        )

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="analysis",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=result.capability_status,
                status_message=user_summary,
                payload={
                    "analysis_type": result.analysis_type,
                    "analysis_run_id": str(result.id) if result.id else None,
                    "model_version_id": str(result.model_version_id) if result.model_version_id else None,
                    "pem_version": result.pem_version,
                    "capability_status": result.capability_status,
                    "capability_label": capability_label(result.capability_status),
                    "result_set_id": str(result_set_id) if result_set_id else None,
                    "result_validation_status": validation_status,
                    "result_validation_label": validation_label(
                        str(validation_status) if validation_status else None
                    ),
                    "integration_execution_id": result.outputs.get("integration_execution_id"),
                    "solver": result.outputs.get("solver"),
                    "solver_status": result.outputs.get("solver_status"),
                    "engineering_results_available": bool(
                        result.outputs.get("engineering_results_available")
                    ),
                    "outputs": result.outputs,
                    "model_summary": result.model_summary,
                    "user_summary": user_summary,
                },
            ),
            confidence=0.8 if result.outputs.get("engineering_results_available") else 0.0,
            recommendations=(
                [
                    "Internal 2D gravity analysis completed. Review member forces before design.",
                    "This is not a 3D ETABS/SAP2000 substitute and does not include wind/seismic.",
                ]
                if result.outputs.get("engineering_results_available")
                else [
                    "Connect an analysis solver adapter before treating results as engineering conclusions.",
                ]
            ),
            validation_information={
                "capability_status": result.capability_status,
                "analysis_status": result.status.value,
                "result_set_id": str(result_set_id) if result_set_id else None,
                "validation_status": validation_status,
            },
        )


class ConcreteDesignAgentHandler:
    agent_type = EngineeringAgentType.CONCRETE_DESIGN_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        aci = _aci_rc_beam_result(
            agent_type=self.agent_type,
            action="concrete_design",
            user_request=user_request,
            parameters=parameters,
            context=context,
            services=self._services,
        )
        if aci is not None:
            return aci
        demo = _demo_rc_beam_result(
            agent_type=self.agent_type,
            action="concrete_design",
            user_request=user_request,
            parameters=parameters,
            context=context,
        )
        if demo is not None:
            return demo
        design_type = str(parameters.get("design_type", "CONCRETE_MEMBER"))
        result = self._services.design_engine.run_design(
            DesignRequest(
                project_id=_project_id(context),
                design_type=design_type,
                parameters=dict(parameters.get("design_parameters", {})),
            )
        )

        result_set_id = result.outputs.get("result_set_id")
        design_available = bool(result.outputs.get("engineering_design_results_available"))
        user_summary = design_user_summary(
            capability_status=result.capability_status,
            message=result.message,
            result_set_id=str(result_set_id) if result_set_id else None,
            design_available=design_available,
        )

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="concrete_design",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=result.capability_status,
                status_message=user_summary,
                payload={
                    "design_type": result.design_type,
                    "design_run_id": str(result.id) if result.id else None,
                    "code_edition": result.code_edition,
                    "pem_version": result.pem_version,
                    "analysis_run_id": str(result.analysis_run_id) if result.analysis_run_id else None,
                    "result_set_id": str(result_set_id) if result_set_id else None,
                    "result_validation_status": result.outputs.get("result_validation_status"),
                    "capability_status": result.capability_status,
                    "capability_label": capability_label(result.capability_status),
                    "engineering_design_results_available": design_available,
                    "outputs": result.outputs,
                    "model_summary": result.model_summary,
                    "user_summary": user_summary,
                },
            ),
            confidence=0.0,
            recommendations=[
                "Connect deterministic design routines before treating results as code-compliant conclusions.",
            ],
            validation_information={
                "capability_status": result.capability_status,
                "design_status": result.status.value,
                "requires_approval": True,
            },
        )


class SteelDesignAgentHandler:
    agent_type = EngineeringAgentType.STEEL_DESIGN_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        aci = _aci_rc_beam_result(
            agent_type=self.agent_type,
            action="steel_design",
            user_request=user_request,
            parameters=parameters,
            context=context,
            services=self._services,
            require_explicit_concrete=True,
        )
        if aci is not None:
            return aci
        steel = _aisc_steel_beam_result(
            agent_type=self.agent_type,
            action="steel_design",
            user_request=user_request,
            parameters=parameters,
            context=context,
            services=self._services,
        )
        if steel is not None:
            return steel
        design_type = str(parameters.get("design_type", "STEEL_MEMBER"))
        result = self._services.design_engine.run_design(
            DesignRequest(
                project_id=_project_id(context),
                design_type=design_type,
                parameters=dict(parameters.get("design_parameters", {})),
            )
        )

        result_set_id = result.outputs.get("result_set_id")
        design_available = bool(result.outputs.get("engineering_design_results_available"))
        user_summary = design_user_summary(
            capability_status=result.capability_status,
            message=result.message,
            result_set_id=str(result_set_id) if result_set_id else None,
            design_available=design_available,
        )

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="steel_design",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=result.capability_status,
                status_message=user_summary,
                payload={
                    "design_type": result.design_type,
                    "design_run_id": str(result.id) if result.id else None,
                    "code_edition": result.code_edition,
                    "pem_version": result.pem_version,
                    "analysis_run_id": str(result.analysis_run_id) if result.analysis_run_id else None,
                    "result_set_id": str(result_set_id) if result_set_id else None,
                    "result_validation_status": result.outputs.get("result_validation_status"),
                    "capability_status": result.capability_status,
                    "capability_label": capability_label(result.capability_status),
                    "engineering_design_results_available": design_available,
                    "outputs": result.outputs,
                    "model_summary": result.model_summary,
                    "user_summary": user_summary,
                },
            ),
            confidence=0.0,
            recommendations=[
                "Connect deterministic design routines before treating results as code-compliant conclusions.",
            ],
            validation_information={
                "capability_status": result.capability_status,
                "design_status": result.status.value,
                "requires_approval": True,
            },
        )


class OptimizationAgentHandler:
    agent_type = EngineeringAgentType.OPTIMIZATION_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        optimization_type = str(parameters.get("optimization_type", "WEIGHT"))
        objective = str(parameters.get("objective", "Minimize structural weight"))
        result = self._services.optimization_engine.run_optimization(
            OptimizationRequest(
                project_id=_project_id(context),
                optimization_type=optimization_type,
                objective=objective,
                constraints=dict(parameters.get("constraints", {})),
                parameters=dict(parameters.get("optimization_parameters", {})),
                analysis_run_id=parameters.get("analysis_run_id"),
                design_run_id=parameters.get("design_run_id"),
            )
        )

        selected = result.outputs.get("selected_candidate")
        user_summary = optimization_user_summary(
            capability_status=result.capability_status,
            message=result.message,
            selected=selected if isinstance(selected, dict) else None,
        )

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="optimization",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=result.capability_status,
                status_message=user_summary,
                payload={
                    "optimization_type": result.optimization_type,
                    "objective": result.objective,
                    "optimization_run_id": str(result.id) if result.id else None,
                    "pem_version": result.pem_version,
                    "analysis_run_id": str(result.analysis_run_id) if result.analysis_run_id else None,
                    "design_run_id": str(result.design_run_id) if result.design_run_id else None,
                    "result_set_id": result.outputs.get("result_set_id"),
                    "result_validation_status": result.outputs.get("result_validation_status"),
                    "capability_status": result.capability_status,
                    "capability_label": capability_label(result.capability_status),
                    "engineering_optimization_results_available": bool(
                        result.outputs.get("engineering_optimization_results_available")
                    ),
                    "selected_candidate": selected,
                    "outputs": result.outputs,
                    "summary": result.message,
                    "user_summary": user_summary,
                    "validation_status": result.validation_summary.get("validation_status"),
                },
            ),
            confidence=0.0,
            recommendations=[
                "Connect deterministic optimization routines before treating results as optimized engineering conclusions.",
            ],
            validation_information={
                "capability_status": result.capability_status,
                "optimization_status": result.status.value,
                "requires_approval": True,
            },
        )


class SeismicAgentHandler:
    agent_type = EngineeringAgentType.SEISMIC_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        code_configuration = context.get("code_configuration") or {}
        missing: list[str] = []
        if not code_configuration:
            missing.append("Seismic code configuration")
        if context.get("pem_version") in (None, 0):
            missing.append("Structural model for lateral system definition")

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="seismic",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status="READY_FOR_SEISMIC_REVIEW",
                status_message="Seismic review scoped to configured standards and project assumptions.",
                payload={
                    "governing_building_code": code_configuration.get("governing_building_code"),
                    "loading_standard": code_configuration.get("loading_standard"),
                    "missing_inputs": missing,
                },
            ),
            confidence=0.35 if not missing else 0.15,
            recommendations=[
                "Confirm site class, importance factor, and lateral system before final seismic decisions.",
            ],
            validation_information={"capability_status": "READY_FOR_SEISMIC_REVIEW"},
        )


class ValidationAgentHandler:
    agent_type = EngineeringAgentType.VALIDATION_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        report = self._services.validation_engine.validate_project(_project_id(context))
        error_count = sum(1 for finding in report.findings if finding.status.value == "ERROR")
        warning_count = sum(
            1 for finding in report.findings if finding.status.value in {"WARNING", "REQUIRES_ENGINEER_REVIEW"}
        )

        capability_status = "PASS" if report.overall_status.value == "PASS" else report.overall_status.value
        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="validation",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=capability_status,
                status_message=report.summary,
                payload={
                    "overall_status": report.overall_status.value,
                    "finding_count": len(report.findings),
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "findings": [finding.model_dump(mode="json") for finding in report.findings[:20]],
                },
            ),
            confidence=0.8 if error_count == 0 else 0.3,
            recommendations=[
                finding.message for finding in report.findings if finding.status.value != "PASS"
            ][:5],
            validation_information={
                "capability_status": capability_status,
                "validation_status": report.overall_status.value,
            },
        )


class CadAgentHandler:
    agent_type = EngineeringAgentType.CAD_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        project_id = _project_id(context)
        drawing_type = str(parameters.get("drawing_type", "FRAMING_PLAN"))
        output_format = CadOutputFormat(str(parameters.get("output_format", "DXF")).upper())
        drawing = self._services.cad_generation_service.generate_drawing(
            CadDrawingRequest(
                project_id=project_id,
                drawing_type=drawing_type,
                output_format=output_format,
            )
        )
        user_summary = drawing.message
        if drawing.status.value == "REQUIRES_LOCAL_SOFTWARE":
            user_summary = "AutoCAD 2027 is not available on this computer. Use DXF export instead."

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="cad",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=drawing.status.value,
                status_message=user_summary,
                payload={
                    "drawing_type": drawing.drawing_type,
                    "drawing_id": str(drawing.id),
                    "output_format": drawing.output_format.value,
                    "validation_status": drawing.validation_status.value,
                    "validation_label": validation_label(drawing.validation_status.value),
                    "file_path": drawing.file_path,
                    "layer_summary": drawing.layer_summary,
                    "capability_label": capability_label(drawing.status.value),
                    "user_summary": user_summary,
                },
            ),
            confidence=0.0,
            generated_artifacts=(
                [
                    {
                        "type": "cad_drawing",
                        "format": drawing.output_format.value,
                        "path": drawing.file_path,
                        "drawing_id": str(drawing.id),
                        "drawing_type": drawing.drawing_type,
                    }
                ]
                if drawing.file_path
                else []
            ),
            recommendations=[
                "Use DXF drawings when AutoCAD is not installed locally.",
            ],
            validation_information={
                "capability_status": drawing.status.value,
                "validation_status": drawing.validation_status.value,
                "drawing_id": str(drawing.id),
                "requires_approval": drawing.validation_status.value == "VALIDATED",
            },
        )


class ReportingAgentHandler:
    agent_type = EngineeringAgentType.REPORTING_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        project_id = _project_id(context)
        report_service = self._services.report_generation_service
        if report_service is None:
            return AgentResult(
                structured_output=_base_output(
                    agent_type=self.agent_type,
                    action="reporting",
                    user_request=user_request,
                    parameters=parameters,
                    context=context,
                    capability_status="UNAVAILABLE",
                    status_message="Report generation service is not configured.",
                    payload={"missing_capability": "report_generation_service"},
                ),
                confidence=0.0,
                validation_information={"capability_status": "UNAVAILABLE"},
            )

        report_type_name = str(parameters.get("report_type", "PROJECT_SUMMARY")).upper()
        try:
            report_type = ReportType(report_type_name)
        except ValueError:
            report_type = ReportType.PROJECT_SUMMARY

        report = report_service.create_report(
            project_id,
            report_type=report_type,
            created_by=str(context.get("actor_id") or "agent"),
        )
        version = report_service.generate_version(
            ReportGenerationRequest(
                project_id=project_id,
                report_id=report.id,
                report_type=report_type,
                requested_by=str(context.get("actor_id") or "agent"),
            )
        )
        missing_data = version.traceability_metadata.get("missing_data", [])
        status_message = "Engineering report generated from persisted platform data."
        if missing_data:
            status_message = (
                "Engineering report generated; missing data explicitly recorded in report metadata."
            )

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="reporting",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status="COMPLETED",
                status_message=status_message,
                payload={
                    "report_id": str(report.id),
                    "report_type": report_type.value,
                    "version": version.version,
                    "missing_data": missing_data,
                    "section_keys": [
                        section.get("key")
                        for section in version.content.get("sections", [])
                        if isinstance(section, dict)
                    ],
                },
            ),
            confidence=0.85 if not missing_data else 0.6,
            generated_artifacts=[
                {
                    "type": "engineering_report",
                    "report_id": str(report.id),
                    "version": version.version,
                    "report_type": report_type.value,
                }
            ],
            recommendations=[
                "Review missing_data entries before issuing the report externally.",
            ]
            if missing_data
            else ["Open the Reports workspace to review the generated version."],
            validation_information={
                "capability_status": "COMPLETED",
                "report_id": str(report.id),
                "version": version.version,
            },
        )


class DocumentInterpretationAgentHandler:
    agent_type = EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT

    def __init__(self, services: EngineeringAgentServices) -> None:
        self._services = services

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        files = context.get("files", [])
        pending = [
            file_item
            for file_item in files
            if str(file_item.get("extraction_status", "")).upper() != "COMPLETED"
        ]
        capability_status = "READY_FOR_DOCUMENT_REVIEW" if files else "MISSING_SOURCE_FILES"

        return AgentResult(
            structured_output=_base_output(
                agent_type=self.agent_type,
                action="document_interpretation",
                user_request=user_request,
                parameters=parameters,
                context=context,
                capability_status=capability_status,
                status_message="Document interpretation scoped to uploaded project files.",
                payload={
                    "files": files,
                    "pending_extraction_count": len(pending),
                },
            ),
            confidence=0.5 if files else 0.1,
            recommendations=[
                "Upload and process source documents before relying on extracted requirements.",
            ]
            if pending or not files
            else ["Review extracted requirements and capture approved decisions in project memory."],
            validation_information={"capability_status": capability_status},
        )


def build_engineering_agent_handlers(
    services: EngineeringAgentServices | None = None,
) -> dict[EngineeringAgentType, EngineeringAgentHandler]:
    if services is None:
        from app.application.service_factory import build_engineering_agent_services

        services = build_engineering_agent_services()

    handlers: list[EngineeringAgentHandler] = [
        StructuralModelingAgentHandler(services),
        LoadAssessmentAgentHandler(services),
        AnalysisAgentHandler(services),
        ConcreteDesignAgentHandler(services),
        SteelDesignAgentHandler(services),
        OptimizationAgentHandler(services),
        SeismicAgentHandler(services),
        ValidationAgentHandler(services),
        CadAgentHandler(services),
        ReportingAgentHandler(services),
        DocumentInterpretationAgentHandler(services),
    ]
    return {handler.agent_type: handler for handler in handlers}


def new_trace_result_id() -> Any:
    return uuid4()
