"""Domain tests for traceability models."""

from app.domain.models.traceability import (
    TraceObjectType,
    TraceabilityRelationshipType,
)


def test_trace_relationship_types_include_core_chain() -> None:
    values = {item.value for item in TraceabilityRelationshipType}
    assert "SOURCE_TO_MEMORY" in values
    assert "DECISION_TO_APPROVAL" in values
    assert "DESIGN_TO_REPORT" in values
    assert "REQUEST_TO_AGENT_EXECUTION" in values


def test_trace_object_types_are_extensible_strings() -> None:
    assert TraceObjectType.FILE.value == "file"
    assert TraceObjectType.DESIGN_RESULT.value == "design_result"
    assert TraceObjectType.AGENT_EXECUTION.value == "agent_execution"
