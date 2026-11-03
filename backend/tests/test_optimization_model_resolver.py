from types import SimpleNamespace
from uuid import uuid4

from app.application.optimization_full.model_resolver import inputs_from_texts, resolve_project_frame
from app.application.optimization_full.project_model import detect_project_model

PID = "00000000-0000-0000-0000-000000000002"


class FakeConv:
    def __init__(self, texts=(), runs=()):
        self.c = SimpleNamespace(id=uuid4(), project_id=PID, title="t")
        self.texts = list(texts)
        self.runs = list(runs)

    def list_project_chat_runs(self, acc, pid):
        return self.runs

    def list_conversations(self, acc, project_id=None, limit=100):
        return [self.c]

    def list_messages(self, cid, acc):
        return [SimpleNamespace(role="user", content=t, created_at=f"2026-01-0{i + 1}") for i, t in enumerate(self.texts)]


def test_nothing_found_builds_default_frame():
    r = resolve_project_frame(FakeConv(), None, PID)
    assert r["source"] == "default"
    assert r["inputs"]["storeys"] == 4 and r["inputs"]["bays_x"] == 3 and r["inputs"]["bay_x_m"] == 5.0
    assert any("اراک" in a for a in r["assumptions_fa"])
    assert resolve_project_frame(FakeConv(), None, PID, include_default=False) is None


def test_frame_description_in_chat_history_is_used():
    conv = FakeConv(texts=["سلام", "قاب ۶ طبقه با ۲×۴ دهانه ۶ متری بساز"])
    r = resolve_project_frame(conv, None, PID)
    assert r["source"] == "chat_text" and r["inputs"]["storeys"] == 6


def test_partial_run_filled_with_defaults():
    conv = FakeConv(runs=[{"kind": "frame3d_analysis", "status": "MISSING_INPUT", "created_at": "x",
                           "inputs": {"storeys": 5, "bays_x": None, "bays_y": None}}])
    r = resolve_project_frame(conv, None, PID)
    assert r["inputs"]["storeys"] == 5 and r["inputs"]["bays_x"] == 3 and "bays_x" in r["assumed"]


def test_detect_never_reports_no_model():
    d = detect_project_model(PID, None, FakeConv())
    assert d["source"] == "default" and d["member_count"] > 0 and d["assumptions_fa"]


def test_inputs_from_texts_none_without_frame():
    assert inputs_from_texts(["hello", "سلام"]) is None


def test_chat_title_reported_for_chat_text_and_runs():
    conv = FakeConv(texts=["قاب ۶ طبقه با ۲×۴ دهانه ۶ متری بساز"])
    conv.c.title = "قاب اراک"
    r = resolve_project_frame(conv, None, PID)
    assert r["chat_title"] == "قاب اراک"
    assert "bay_x_m" not in r["assumed"] and "storey_height_m" in r["assumed"]
    run = {"kind": "frame3d_analysis", "status": "MISSING_INPUT", "created_at": "x", "conversation_title": "c1",
           "inputs": {"storeys": 13, "bays_x": None, "bays_y": None}}
    r2 = resolve_project_frame(FakeConv(runs=[run]), None, PID)
    assert r2["chat_title"] == "c1" and r2["inputs"]["storeys"] == 13
    assert resolve_project_frame(FakeConv(), None, PID)["chat_title"] is None


def test_project_frame_route_splits_chat_and_assumed():
    from app.api.routes.optimization_full import project_frame

    class Access:
        def require_project(self, pid, acc):
            return None

    conv = FakeConv(texts=["قاب ۶ طبقه با ۲×۴ دهانه ۶ متری بساز"])
    out = project_frame(PID, None, conv, Access())
    assert out["source"] == "chat_text" and "storeys" in out["from_chat"] and "storey_height_m" in out["assumed"]
    d = project_frame(PID, None, FakeConv(), Access())
    assert d["source"] == "default" and d["from_chat"] == [] and d["inputs"]["storeys"] == 4


def test_export_limit_message_names_value_and_limit():
    import pytest

    from app.application.frame3d_chat_analysis import MAX_BAYS, run_frame3d_for_export

    with pytest.raises(ValueError) as e:
        run_frame3d_for_export({"storeys": 3, "bays_x": 100, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 5, "storey_height_m": 3.2})
    msg = str(e.value)
    assert "100" in msg and f"1–{MAX_BAYS}" in msg and "مجاز" in msg
