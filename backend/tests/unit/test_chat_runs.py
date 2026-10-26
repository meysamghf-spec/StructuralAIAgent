from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.application.chat_runs import extract_runs


def _msg(role, md):
    return SimpleNamespace(id=uuid4(), role=role, metadata=md, created_at=datetime.now(timezone.utc))


def test_extract_runs_kinds():
    conv = SimpleNamespace(id=uuid4(), title="t")
    msgs = [
        _msg("user", {"engineering_results": {"kind": "frame3d_analysis"}}),
        _msg("assistant", {"mode": "agent_execution", "engineering_results": {"kind": "frame3d_analysis", "results": {"period_s": 0.8}}}),
        _msg("assistant", {"autocad_result": {"job_id": "j1", "filename": "a.dxf"}}),
        _msg("assistant", {}),
    ]
    runs = extract_runs(conv, msgs)
    kinds = [r["kind"] for r in runs]
    assert "frame3d_analysis" in kinds and "autocad" in kinds
    assert len([k for k in kinds if k == "frame3d_analysis"]) == 1
    assert all(r["conversation_id"] == str(conv.id) for r in runs)
