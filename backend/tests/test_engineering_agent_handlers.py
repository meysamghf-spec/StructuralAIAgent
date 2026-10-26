"""Tests for specialized engineering agent handlers."""

from uuid import uuid4

from app.application.engineering_agent_handlers import (
    AnalysisAgentHandler,
    CadAgentHandler,
    ReportingAgentHandler,
    ValidationAgentHandler,
    build_engineering_agent_handlers,
)
from app.application.service_factory import (
    build_engineering_agent_services,
    build_project_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.cad import CadDrawingType, CadOutputFormat
from tests.integration.helpers import populate_standard_pem


def _context(project_id) -> dict:
    return {
        "project_id": str(project_id),
        "project_name": "Handler Test Project",
        "pem_version": None,
        "code_configuration": None,
        "unit_configuration": None,
        "memory_total_count": 0,
        "memories": [],
        "files": [],
    }


def test_validation_agent_runs_deterministic_validation(db_session: str) -> None:
    project = build_project_service().create_project(name="Validation Handler Project")
    services = build_engineering_agent_services()
    handler = ValidationAgentHandler(services)

    result = handler.execute(
        user_request="Validate project readiness",
        parameters={},
        context=_context(project.project.id),
    )

    assert result.structured_output["action"] == "validation"
    assert result.structured_output["finding_count"] >= 0
    assert result.validation_information["validation_status"] in {
        "ERROR",
        "WARNING",
        "REQUIRES_ENGINEER_REVIEW",
        "PASS",
    }
    assert "stub" not in result.validation_information


def test_analysis_agent_reports_not_implemented_solver(db_session: str) -> None:
    project = build_project_service().create_project(name="Analysis Handler Project")
    handler = AnalysisAgentHandler(build_engineering_agent_services())

    result = handler.execute(
        user_request="Run drift analysis",
        parameters={"analysis_type": "LATERAL_DRIFT"},
        context=_context(project.project.id),
    )

    assert result.structured_output["capability_status"] == "MODEL_NOT_READY"
    assert "member" in result.structured_output["status_message"].lower() or "model" in result.structured_output["status_message"].lower()


def test_build_handlers_registers_all_specialized_agents() -> None:
    handlers = build_engineering_agent_handlers()
    expected = {
        EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
        EngineeringAgentType.LOAD_ASSESSMENT_AGENT,
        EngineeringAgentType.ANALYSIS_AGENT,
        EngineeringAgentType.CONCRETE_DESIGN_AGENT,
        EngineeringAgentType.STEEL_DESIGN_AGENT,
        EngineeringAgentType.OPTIMIZATION_AGENT,
        EngineeringAgentType.SEISMIC_AGENT,
        EngineeringAgentType.VALIDATION_AGENT,
        EngineeringAgentType.CAD_AGENT,
        EngineeringAgentType.REPORTING_AGENT,
        EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
    }
    assert expected.issubset(set(handlers.keys()))


def test_cad_agent_generated_artifacts_are_structured_dicts(db_session: str) -> None:
    project = build_project_service().create_project(name="CAD Handler Project")
    populate_standard_pem(project.project.id)
    services = build_engineering_agent_services()
    handler = CadAgentHandler(services)

    result = handler.execute(
        user_request="Generate framing plan",
        parameters={"drawing_type": CadDrawingType.FRAMING_PLAN.value, "output_format": "DXF"},
        context=_context(project.project.id),
    )

    assert result.generated_artifacts
    artifact = result.generated_artifacts[0]
    assert isinstance(artifact, dict)
    assert artifact["type"] == "cad_drawing"
    assert artifact["format"] == CadOutputFormat.DXF.value
    assert isinstance(artifact["path"], str)


def test_reporting_agent_generates_persisted_report(db_session: str) -> None:
    project = build_project_service().create_project(name="Reporting Handler Project")
    handler = ReportingAgentHandler(build_engineering_agent_services())

    result = handler.execute(
        user_request="Generate project summary report",
        parameters={"report_type": "PROJECT_SUMMARY"},
        context=_context(project.project.id),
    )

    assert result.structured_output["capability_status"] == "COMPLETED"
    assert result.generated_artifacts
    assert result.generated_artifacts[0]["type"] == "engineering_report"
    assert result.structured_output["report_id"]
