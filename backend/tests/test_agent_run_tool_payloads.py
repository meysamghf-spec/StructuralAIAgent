"""Richer agent_run.tool payloads from real attachment and handler facts."""

from uuid import uuid4

from app.application.agent_orchestration_service import AgentOrchestrationService
from app.application.agent_run_events import EVENT_FAILED, EVENT_TOOL, EVENT_VALIDATION
from app.application.agent_run_tool_payloads import (
    capability_tool_payload,
    document_tool_payload,
    iter_document_tool_events,
)
from app.application.agent_run_view import build_agent_run_view
from app.application.service_factory import (
    build_agent_orchestration_service,
    build_project_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionRequest,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
)


class _RecordingSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))


def _document_attachment(**overrides) -> dict:
    payload = {
        "file_id": str(uuid4()),
        "filename": "plans.pdf",
        "file_type": "PDF",
        "availability": "indexed",
        "extraction_status": "COMPLETE",
        "extraction_metadata": {"page_count": 18},
        "indexed_memory_ids": ["m1", "m2", "m3", "m4"],
    }
    payload.update(overrides)
    return payload


def test_document_tool_event_includes_real_file_and_page_count() -> None:
    payload = document_tool_payload([_document_attachment()], status="complete")
    assert payload["id"] == "document_analysis"
    assert payload["capability"] == "DOCUMENT_READ"
    assert payload["files"][0]["filename"] == "plans.pdf"
    assert payload["files"][0]["page_count"] == 18
    assert "DOCUMENT_DISCOVERED" in payload["operations"]
    assert "DOCUMENT_INDEXED" in payload["operations"]
    assert "DOCUMENT_SEARCHED" in payload["operations"]
    labels = [item["label"] for item in payload["details"]]
    assert "plans.pdf" in labels
    assert "18 pages" in labels
    assert "Indexed" in labels
    assert "4 relevant sections found" in labels
    serialized = str(payload)
    assert "C:\\" not in serialized
    assert "/var/" not in serialized
    assert "password" not in serialized.lower()


def test_page_count_omitted_when_parser_did_not_provide_it() -> None:
    payload = document_tool_payload(
        [
            _document_attachment(
                extraction_metadata={"parser": "unknown"},
                structured_preview={"headings": ["Scope"]},
            )
        ],
        status="complete",
    )
    assert payload["files"][0]["page_count"] is None
    assert not any("page" in item["label"].lower() for item in payload["details"])


def test_indexing_event_omitted_when_file_was_not_indexed() -> None:
    payload = document_tool_payload(
        [
            {
                "filename": "scan.png",
                "file_type": "IMAGE",
                "availability": "stored_only",
                "extraction_status": "NOT_STARTED",
            }
        ],
        status="complete",
    )
    assert payload["operations"] == ["DOCUMENT_DISCOVERED"]
    assert "DOCUMENT_INDEXED" not in payload["operations"]
    assert payload["counts"]["relevant_sections"] == 0


def test_document_events_are_granular_but_share_one_tool_id() -> None:
    events = iter_document_tool_events([_document_attachment()])
    assert len(events) >= 2
    assert {event["id"] for event in events} == {"document_analysis"}
    assert events[0]["operation"] == "DOCUMENT_DISCOVERED"
    assert events[-1]["status"] == "complete"


def test_engineering_tool_event_uses_real_model_summary_only() -> None:
    result = AgentResult(
        structured_output={
            "analysis_type": "LATERAL_DRIFT",
            "model_summary": {"member_count": 42, "load_combination_count": 8},
            "engineering_results_available": True,
        },
        generated_artifacts=[{"type": "analysis_result", "name": "Lateral drift results"}],
    )
    payload = capability_tool_payload(
        agent_type=EngineeringAgentType.ANALYSIS_AGENT.value,
        status="complete",
        agent_result=result,
        validation_status="PASS",
    )
    assert payload["name"] == "Structural Analysis"
    labels = [item["label"] for item in payload["details"]]
    assert "Model loaded" in labels
    assert "42 members in model" in labels
    assert "8 load combinations found" in labels
    assert payload["counts"]["members"] == 42
    assert payload["artifacts"][0]["name"] == "Lateral drift results"
    assert payload["artifacts"][0]["artifact_type"] == "analysis_result"
    assert any("Validation: Pass" in item["label"] for item in payload["details"])


def test_aci_rc_beam_tool_event_uses_real_check_outcomes() -> None:
    payload = capability_tool_payload(
        agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT.value,
        status="complete",
        agent_result=AgentResult(
            structured_output={
                "aci_rc_beam": {
                    "kind": "aci_rc_beam",
                    "status": "PASS",
                    "results": {"flexure_outcome": "PASS", "shear_outcome": "PASS"},
                }
            }
        ),
        validation_status="PASS",
    )
    labels = [item["label"] for item in payload["details"]]
    assert any("ACI 318 RC beam flexure and shear check completed" in label for label in labels)
    assert "Flexure PASS" in labels
    assert "Shear PASS" in labels
    assert "ENGINEERING_CODE_CHECK" in payload["operations"]
    assert "members" not in payload["counts"]


def test_engineering_tool_event_does_not_invent_member_counts() -> None:
    payload = capability_tool_payload(
        agent_type=EngineeringAgentType.ANALYSIS_AGENT.value,
        status="complete",
        agent_result=AgentResult(structured_output={"capability_label": "Completed"}),
    )
    assert "members" not in payload["counts"]
    assert "load_combinations" not in payload["counts"]
    assert not any("member" in item["label"].lower() for item in payload["details"])


def test_artifact_metadata_strips_filesystem_paths() -> None:
    payload = capability_tool_payload(
        agent_type=EngineeringAgentType.CAD_AGENT.value,
        status="complete",
        agent_result=AgentResult(
            structured_output={"drawing_type": "FRAMING_PLAN"},
            generated_artifacts=[
                {
                    "type": "cad_drawing",
                    "name": "Framing DXF",
                    "path": "C:\\secrets\\drawings\\frame.dxf",
                    "file_path": "/var/data/frame.dxf",
                    "drawing_id": "draw-1",
                    "api_key": "should-not-appear",
                }
            ],
        ),
    )
    serialized = str(payload)
    assert "C:\\secrets" not in serialized
    assert "/var/data" not in serialized
    assert "api_key" not in serialized
    assert payload["artifacts"][0]["id"] == "draw-1"


def test_safe_tool_error_hides_sensitive_text() -> None:
    payload = capability_tool_payload(
        agent_type=EngineeringAgentType.ANALYSIS_AGENT.value,
        status="error",
        error_message="Traceback (most recent call last): password=hunter2 token=abc",
    )
    assert payload["status"] == "error"
    assert "traceback" not in payload["error"]["reason"].lower()
    assert "password" not in payload["error"]["reason"].lower()
    assert "token" not in payload["error"]["reason"].lower()


def test_agent_run_view_includes_rich_document_and_artifact_fields() -> None:
    record = AgentExecutionRecord(
        id=uuid4(),
        project_id=uuid4(),
        agent_definition_id=uuid4(),
        agent_version=1,
        execution_status=AgentExecutionStatus.COMPLETED,
        input_request={
            "user_request": "Analyze the uploaded model.",
            "parameters": {
                "conversation_id": str(uuid4()),
                "attachment_context": {"attachments": [_document_attachment()]},
            },
        },
        prompt_generation={"selected_agent_type": EngineeringAgentType.ANALYSIS_AGENT.value},
        agent_result=AgentResult(
            structured_output={
                "demo_rc_beam": {"kind": "demo_rc_beam"},
            },
            generated_artifacts=[{"type": "demo_calculation", "name": "RC beam Demo analysis"}],
        ),
        validation_status=AgentValidationStatus.PASS,
    )
    view = build_agent_run_view(record)
    document = next(tool for tool in view["tools"] if tool["id"] == "document_analysis")
    analysis = next(tool for tool in view["tools"] if tool["capability"] == "ANALYSIS_AGENT")
    assert document["files"][0]["page_count"] == 18
    assert analysis["artifacts"][0]["name"] == "RC beam Demo analysis"
    assert any("Deterministic beam analysis completed" in item["label"] for item in analysis["details"])


def test_orchestration_emits_ordered_real_tool_events_then_validation(
    db_session: str,
) -> None:
    project = build_project_service().create_project(name="Rich Tool Events")
    orchestration = build_agent_orchestration_service()
    sink = _RecordingSink()
    record = orchestration.orchestrate(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request=(
                "Analyze a simply supported reinforced concrete beam with a 6 m span "
                "and uniform load of 20 kN/m."
            ),
            requires_approval=False,
            parameters={
                "attachment_context": {"attachments": [_document_attachment()]},
            },
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
        progress_sink=sink,
    )
    assert record.execution_status == AgentExecutionStatus.COMPLETED
    types = [event_type for event_type, _payload in sink.events]
    assert EVENT_FAILED not in types
    assert EVENT_VALIDATION in types
    tool_events = [payload["tool"] for event_type, payload in sink.events if event_type == EVENT_TOOL]
    document_events = [tool for tool in tool_events if tool["id"] == "document_analysis"]
    analysis_events = [tool for tool in tool_events if tool.get("capability") == "ANALYSIS_AGENT"]
    assert document_events
    assert document_events[0]["operation"] == "DOCUMENT_DISCOVERED"
    assert document_events[-1]["status"] == "complete"
    assert document_events[-1]["files"][0]["filename"] == "plans.pdf"
    assert document_events[-1]["files"][0]["page_count"] == 18
    assert analysis_events
    assert analysis_events[0]["status"] == "current"
    assert analysis_events[-1]["status"] == "complete"
    assert any(
        item["label"] == "Deterministic beam analysis completed"
        for item in analysis_events[-1]["details"]
    )
    first_document = types.index(EVENT_TOOL)
    first_validation = types.index(EVENT_VALIDATION)
    assert first_document < first_validation
    serialized = str(sink.events)
    assert "password" not in serialized.lower()
    assert "traceback" not in serialized.lower()
    assert "api_key" not in serialized.lower()


def test_orchestration_service_is_not_replaced_by_a_second_runtime() -> None:
    assert hasattr(AgentOrchestrationService, "orchestrate")
