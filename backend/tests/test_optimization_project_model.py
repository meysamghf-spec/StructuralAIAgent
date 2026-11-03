from types import SimpleNamespace

from app.application.optimization_checklist import checklist_for_project_model
from app.application.optimization_full.project_model import detect_project_model, frame_member_count


def test_frame_member_count():
    assert frame_member_count({"storeys": 2, "bays_x": 1, "bays_y": 1}) == 2 * (4 + 4)
    assert frame_member_count({}) == 0


def test_detects_import_before_frame(monkeypatch):
    import json
    from datetime import datetime

    rec = SimpleNamespace(filename="m.saia-import.json", created_at=datetime(2026, 1, 1), id="r1")
    registry = SimpleNamespace(list_project_files=lambda pid: [rec])
    state = {"model": {"counts": {"members": 12, "combos": 3, "sections": 2, "load_patterns": 2}}}
    files = SimpleNamespace(get_file_content=lambda pid, rid: (None, json.dumps(state).encode()))
    pid = "00000000-0000-0000-0000-000000000001"
    d = detect_project_model(pid, None, None, registry, files)
    assert d["source"] == "model" and d["member_count"] == 12 and d["load_combination_count"] == 3


def test_detects_chat_frame(monkeypatch):
    import app.api.routes.autocad as ac

    monkeypatch.setattr(ac, "latest_frame_inputs", lambda conv, acc, pid: {"storeys": 3, "bays_x": 2, "bays_y": 2})
    d = detect_project_model("00000000-0000-0000-0000-000000000001", None, object())
    assert d["source"] == "frame" and d["member_count"] == 3 * (9 + 12)
    assert detect_project_model(None, None, object()) is None


def test_checklist_for_project_model_ready():
    c = checklist_for_project_model({"member_count": 10, "label": {"en": "x", "fa": "y"}}, "p")
    assert c["ready"] and not c["missing_keys"]
