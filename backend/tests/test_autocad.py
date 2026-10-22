from app.application.autocad import service as cad_service
from app.application.autocad.chat_intent import run_chat_autocad, wants_prompt, wants_vectorize
from app.application.autocad.floor_plan import generate_from_prompt
from app.application.autocad.preview import dxf_to_svg
from app.application.autocad.standards import SHEET_REGISTRY


def test_prompt_to_plan_en_fa():
    for p in ["3-storey residential building 12x20 m", "ساختمان مسکونی ۴ طبقه ۱۵ در ۲۵ متر"]:
        doc, s = generate_from_prompt(p)
        assert s["spaces"] > 0 and "<svg" in dxf_to_svg(doc)
        assert {"A-WALL-EXTR", "S-GRID", "A-ANNO-TTLB"} <= {e.dxf.layer for e in doc.modelspace()}


def test_chat_intent():
    assert wants_vectorize("convert this to DXF", ["plan.pdf"])
    assert wants_vectorize("این نقشه را به اتوکد تبدیل کن", ["photo.jpg"])
    assert not wants_vectorize("what loads are in this report?", ["report.pdf"])
    assert wants_prompt("draw a DXF plan for a 2 bedroom apartment 12x20")
    assert wants_prompt("یک نقشه آپارتمان دو خوابه ۱۲ در ۲۰ بکش")
    assert not wants_prompt("simply supported beam 6 m")
    assert not wants_prompt("3 storey 3x3 bay concrete frame, export ETABS")


def test_chat_runs_prompt_and_saves_project_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cad_service, "_root", lambda: tmp_path)
    saved = {}
    out = run_chat_autocad("draw a floor plan for a 2 bedroom apartment 12x15 m", [], owner="u1", project_id="p1",
                           save_project_file=lambda n, b: saved.setdefault("id", n) and "file-1")
    assert out is not None
    md, meta = out
    r = meta["autocad_result"]
    assert r["project_file_id"] == "file-1" and r["filename"].endswith(".dxf")
    assert cad_service.list_jobs("u1", "p1")[0]["id"] == r["job_id"]
    assert run_chat_autocad("simply supported beam 6 m", [], owner="u1", project_id=None) is None


def test_registry_has_future_sheets():
    assert any(not s.implemented for s in SHEET_REGISTRY)
