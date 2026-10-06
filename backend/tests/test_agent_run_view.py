"""Unit tests for structured agent-run views derived from existing executions."""

from uuid import uuid4

from app.application.agent_run_view import build_agent_run_view, chat_mode_to_agent_type
from app.application.conversation_service import _format_execution_response
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
)


def _record(**overrides) -> AgentExecutionRecord:
    defaults = dict(
        id=uuid4(),
        project_id=uuid4(),
        agent_definition_id=uuid4(),
        agent_version=1,
        execution_status=AgentExecutionStatus.COMPLETED,
        input_request={
            "user_request": "Analyze the uploaded ETABS model.",
            "parameters": {
                "conversation_id": str(uuid4()),
                "attachment_context": {
                    "attachments": [
                        {
                            "filename": "plans.pdf",
                            "file_type": "PDF",
                            "availability": "indexed",
                            "extraction_metadata": {"page_count": 18},
                        }
                    ]
                },
            },
        },
        prompt_generation={"selected_agent_type": EngineeringAgentType.ANALYSIS_AGENT.value},
        agent_result=AgentResult(
            structured_output={"status": "completed"},
            generated_artifacts=[{"type": "engineering_report", "name": "Analysis Report"}],
            recommendations=["Review critical members"],
            validation_information={"warnings": []},
        ),
        validation_status=AgentValidationStatus.PASS,
    )
    defaults.update(overrides)
    return AgentExecutionRecord(**defaults)


def test_completed_run_maps_real_lifecycle_steps() -> None:
    view = build_agent_run_view(_record())
    assert view["lifecycle"] == "completed"
    states = {step["key"]: step["state"] for step in view["steps"]}
    assert states["understand"] == "complete"
    assert states["project_context"] == "complete"
    assert states["documents"] == "complete"
    assert states["execute"] == "complete"
    assert states["validate"] == "complete"
    assert states["respond"] == "complete"
    assert "approval" not in states
    assert view["context"]["conversation"] is True
    assert view["context"]["indexed_document_count"] == 1
    assert view["context"]["files"][0]["filename"] == "plans.pdf"


def test_document_step_omitted_when_no_attachments() -> None:
    view = build_agent_run_view(
        _record(
            input_request={
                "user_request": "Analyze a simply supported beam.",
                "parameters": {"conversation_id": str(uuid4())},
            }
        )
    )
    keys = [step["key"] for step in view["steps"]]
    assert "documents" not in keys
    assert view["context"]["files"] == []


def test_awaiting_approval_marks_approval_current() -> None:
    view = build_agent_run_view(
        _record(
            execution_status=AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL,
            approval_request_id=uuid4(),
            prompt_generation={"selected_agent_type": EngineeringAgentType.CONCRETE_DESIGN_AGENT.value},
        )
    )
    assert view["lifecycle"] == "waiting_for_approval"
    assert view["requires_approval"] is True
    states = {step["key"]: step["state"] for step in view["steps"]}
    assert states["execute"] == "complete"
    assert states["approval"] == "current"
    assert states["respond"] == "pending"


def test_failed_execution_exposes_safe_error() -> None:
    view = build_agent_run_view(
        _record(
            execution_status=AgentExecutionStatus.FAILED,
            error_metadata={"message": "Unsupported ETABS version or corrupted file."},
            agent_result=None,
            validation_status=AgentValidationStatus.ERROR,
        )
    )
    assert view["lifecycle"] == "failed"
    states = {step["key"]: step["state"] for step in view["steps"]}
    assert states["execute"] == "error"
    assert view["error"]["title"] == "Engineering workflow failed"
    assert "Unsupported ETABS" in view["error"]["reason"]
    assert "Traceback" not in view["error"]["reason"]


def test_tools_use_capability_catalog_not_a_second_registry() -> None:
    view = build_agent_run_view(_record())
    names = [tool["name"] for tool in view["tools"]]
    assert "Document Analysis" in names
    assert "Structural Analysis" in names
    analysis = next(tool for tool in view["tools"] if tool["name"] == "Structural Analysis")
    assert analysis["capability"] == "ANALYSIS_AGENT"
    assert any("engineering.analysis.run" in item["label"] for item in analysis["details"])
    document = next(tool for tool in view["tools"] if tool["id"] == "document_analysis")
    assert document["files"][0]["filename"] == "plans.pdf"
    assert document["files"][0]["page_count"] == 18
    assert any(item["label"] == "Indexed" for item in document["details"])


def test_chat_mode_maps_only_unambiguous_catalog_types() -> None:
    assert chat_mode_to_agent_type("analyze") == EngineeringAgentType.ANALYSIS_AGENT
    assert chat_mode_to_agent_type("cad") == EngineeringAgentType.CAD_AGENT
    assert chat_mode_to_agent_type("documents") == EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT
    assert chat_mode_to_agent_type("reports") == EngineeringAgentType.REPORTING_AGENT
    assert chat_mode_to_agent_type("auto") is None
    assert chat_mode_to_agent_type("design") is None
    assert chat_mode_to_agent_type("unknown") is None


def test_format_execution_response_includes_agent_run_metadata() -> None:
    content, metadata = _format_execution_response(_record())
    assert metadata["mode"] == "agent_execution"
    assert metadata["agent_run"]["lifecycle"] == "completed"
    assert metadata["status_events"][0] == "Building engineering context"
    assert "Validating results" in metadata["status_events"]
    assert "Status" in content
