from app.application.autocad.chat_intent import autocad_chat_reply
from app.application.autocad.floor_plan import generate_from_prompt
from app.application.autocad.preview import dxf_to_svg
from app.application.autocad.standards import SHEET_REGISTRY


def test_prompt_to_plan_en_fa():
    for p in ["3-storey residential building 12x20 m", "ساختمان مسکونی ۴ طبقه ۱۵ در ۲۵ متر"]:
        doc, s = generate_from_prompt(p)
        assert s["spaces"] > 0 and "<svg" in dxf_to_svg(doc)
        assert {"A-WALL-EXTR", "S-GRID", "A-ANNO-TTLB"} <= {e.dxf.layer for e in doc.modelspace()}


def test_chat_intent():
    assert "Integrations" in autocad_chat_reply("convert this PDF to DXF")
    assert "cad_prompt" in autocad_chat_reply("draw a DXF plan for a 3 storey building 12x20")
    assert autocad_chat_reply("simply supported beam 6 m") is None


def test_registry_has_future_sheets():
    assert any(not s.implemented for s in SHEET_REGISTRY)
