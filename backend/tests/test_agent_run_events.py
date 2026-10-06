"""Unit tests for the agent-run SSE contract."""

from app.application.agent_run_events import (
    EVENT_STEP,
    encode_sse,
    parse_sse_stream,
    safe_stream_error,
)


def test_encode_and_parse_sse_round_trip() -> None:
    encoded = encode_sse(EVENT_STEP, {"run_id": "abc", "step_id": "execute", "status": "current"})
    events = parse_sse_stream(encoded)
    assert events == [(EVENT_STEP, {"run_id": "abc", "step_id": "execute", "status": "current"})]


def test_parse_sse_skips_malformed_json() -> None:
    body = "event: agent_run.step\ndata: {not-json\n\n"
    assert parse_sse_stream(body) == []


def test_safe_stream_error_strips_sensitive_text() -> None:
    error = safe_stream_error(title="Failed", reason="Traceback (most recent call last): secret token=abc")
    assert "traceback" not in error["reason"].lower()
    assert "token" not in error["reason"].lower()
