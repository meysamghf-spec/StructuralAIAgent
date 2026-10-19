"""Rebar detailing DXF (Phase 6a): parsing, code formulas, stock-length splitting, ezdxf audit, schedule totals, chat routing."""

from __future__ import annotations

import io

import ezdxf
import pytest

from app.application import csi_text_export as cte
from app.application.frame3d_chat_analysis import (
    build_frame3d_payload,
    is_export_request,
    requested_export_formats,
    run_frame3d_for_export,
)
from app.application.rebar_detailing import (
    STOCK_LENGTH_MM,
    build_rebar_doc,
    dev_length,
    hook_length,
    lap_length,
    parse_bars,
    parse_spacing,
    split_bar,
    unit_weight,
    zone_positions,
)

INPUTS = {"storeys": 3, "bays_x": 3, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 4, "storey_height_m": 3.2, "design_code": "MABHAS9"}


@pytest.fixture(scope="module")
def model():
    p = build_frame3d_payload("", manual_inputs=INPUTS)
    return run_frame3d_for_export(p["inputs"])


def test_parsers():
    assert parse_bars("3Φ14") == (3, 14)
    assert parse_spacing("Φ10@95 (2h = 900 mm), Φ10@175 elsewhere") == (10, 95, 175, 900)
    assert parse_spacing("Φ10@125 over l0 = 458 mm at both ends, Φ10@250 elsewhere") == (10, 125, 250, 458)


def test_code_lengths():
    # ld = fy/(2.1 sqrt fc) db for db<=18: 400/(2.1*5.477)*16 = 556 -> 560 ; top bars x1.3
    assert dev_length(16, 400, 30) == 560
    assert dev_length(16, 400, 30, top=True) == 730
    assert dev_length(20, 400, 30) == 860  # /1.7
    assert hook_length(16, 400, 30) == 290  # 0.24*400/5.477*16 = 280.4 -> >= 8db
    assert lap_length(16, 400, 30) == 730
    assert round(unit_weight(16), 3) == 1.580


def test_split_bar_respects_stock_length_and_lap_locations():
    pieces = split_bar(15400, 800, [2500, 7500, 12500])
    assert all(e - a <= STOCK_LENGTH_MM for a, e in pieces)
    assert pieces[0][1] - pieces[1][0] == 800  # lap overlap
    assert split_bar(9000, 800, [4500]) == [(0.0, 9000)]


def test_zone_positions_spacing_limits():
    xs = zone_positions(0, 4600, 900, 95, 175)
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    assert max(gaps) <= 175 + 1e-6 and xs[0] == 50 and xs[-1] == 4550
    assert all(g <= 95 + 1e-6 for a, g in zip(xs, gaps) if a + g <= 900)  # inside the 2h zone


def test_dxf_audits_clean_and_has_three_sheets(model):
    inp, raw, design = model
    text = cte.build_export("dxf_rebar", inp, raw, design)
    doc = ezdxf.read(io.StringIO(text))
    assert len(doc.audit().errors) == 0
    msp = doc.modelspace()
    titles = [e.dxf.text for e in msp.query("TEXT[layer=='TITLE']")]
    assert len(titles) == 3 and any("BENDING SCHEDULE" in t for t in titles)
    assert len(msp.query("LINE[layer=='REBAR_STIRRUP']")) > 100
    assert any("وزن کل" in e.dxf.text for e in msp.query("TEXT"))


def test_schedule_rows_and_total(model):
    inp, _, design = model
    _, rows, total = build_rebar_doc(inp, design)
    assert {r.mark.split("-")[-1][:2] for r in rows} >= {"T1", "B1", "S1", "V1", "H1"}
    assert all(r.length_mm <= STOCK_LENGTH_MM for r in rows)
    assert abs(total - sum(r.weight_kg for r in rows)) < 1e-6
    area = inp.bays_x * inp.bay_x_m * inp.bays_y * inp.bay_y_m * inp.storeys
    assert 5 < total / area < 60  # beams + columns kg/m2 plausibility


def test_requires_design():
    p = build_frame3d_payload("", manual_inputs={**INPUTS, "design_code": "NONE"})
    inp, raw, design = run_frame3d_for_export(p["inputs"])
    with pytest.raises(ValueError):
        cte.build_export("dxf_rebar", inp, raw, design)


def test_chat_phrase_routes_to_rebar_export():
    assert requested_export_formats("نقشه آرماتوربندی") == ["dxf_rebar"]
    assert is_export_request("نقشه آرماتوربندی بده")
    assert "dxf_rebar" not in requested_export_formats("export autocad plans for the frame")
    prior = {k: v for k, v in INPUTS.items() if k != "design_code"}
    payload = build_frame3d_payload("نقشه آرماتوربندی", prior_spec=prior)
    assert any(e["format"] == "dxf_rebar" and e["requested"] for e in payload["exports"])


# ---------------------------------------------------------------- chat-changeable assumptions
from app.application import detailing_assumptions as da  # noqa: E402
from app.application.frame3d_chat_analysis import frame3d_markdown  # noqa: E402
from app.application.rebar_detailing import cutoff_length  # noqa: E402


def test_parse_persian_example():
    a, inp = da.parse_assumptions("پوشش ۵۰ میلی‌متر، شاخه ۱۲ متری، قطع آرماتور در ln/4")
    assert a == {"cover_mm": 50.0, "stock_length_m": 12.0, "cutoff": "ln/4"} and inp == {}


def test_parse_english_full_set():
    a, inp = da.parse_assumptions(
        "cover 5 cm, 9 m stock bars, cut-off from the moment diagram, lap splice class A, ld factor 1.2, hook factor 1.1, "
        "psi_t=1.0, cross-ties alternate, stirrup hooks 12 db, stirrups Φ12, fy=420 fc=28, beam bars 16, 20, 25, "
        "column bars Φ18/Φ22, special ductility, SCWB skip")
    assert a["cover_mm"] == 50 and a["stock_length_m"] == 9 and a["cutoff"] == "moment" and a["splice_class"] == "A"
    assert a["ld_factor"] == 1.2 and a["hook_factor"] == 1.1 and a["psi_t"] == 1.0 and a["cross_ties"] == "alternate"
    assert a["stirrup_hook_db"] == 12 and a["stirrup_db"] == 12 and a["beam_bars"] == [16, 20, 25] and a["column_bars"] == [18, 22]
    assert a["ductility"] == "special" and a["scwb"] == "skip"
    assert inp == {"system": "RC_SMF", "fy_mpa": 420.0, "fc_mpa": 28.0}


def test_parse_persian_set_and_no_false_positive():
    a, inp = da.parse_assumptions("وصله کلاس الف، سنجاقی یکی در میان، قلاب خاموت ۶ برابر، شکل پذیری متوسط، ستون قوی تیر ضعیف اعمال نشود، میلگردهای تیر ۱۴ و ۱۸، مقاومت بتن ۳۰")
    assert a == {"splice_class": "A", "cross_ties": "alternate", "stirrup_hook_db": 6, "beam_bars": [14, 18],
                 "ductility": "intermediate", "scwb": "skip"}
    assert inp == {"system": "RC_IMF", "fc_mpa": 30.0}
    assert da.parse_assumptions("design the beams of the frame") == ({}, {})
    assert da.is_show_assumptions("فرض‌ها را نشان بده") and da.is_show_assumptions("show assumptions")


def test_cutoff_rules():
    assert cutoff_length("ln/3", 4600, 60, 30, 3, 2, 390, 16) == 1540
    assert cutoff_length("ln/4", 4600, 60, 30, 3, 2, 390, 16) == 1150
    x = cutoff_length("moment", 4600, 60, 30, 3, 2, 390, 16)
    assert 4600 / 16 <= x < 4600 / 2


def test_assumptions_persist_and_apply_on_next_run():
    prior = {k: v for k, v in INPUTS.items()}
    p1 = build_frame3d_payload("پوشش ۵۰ میلی‌متر، شاخه ۱۰ متری، قطع آرماتور در ln/4، خاموت Φ12", prior_spec=prior)
    assert p1["status"] == "completed" and p1["model_from_project_memory"]
    assert p1["inputs"]["assumptions"] == {"cover_mm": 50.0, "stock_length_m": 10.0, "cutoff": "ln/4", "stirrup_db": 12}
    assert "Φ12@" in p1["design"]["beams"][0]["stirrups"]  # stirrup Φ applied in the Mabhas 9 design
    md = frame3d_markdown(p1)
    assert "پوشش بتن: 50 mm *" in md and "قطع آرماتور فوقانی: ln/4 *" in md
    # next run: spec from memory keeps the assumptions; rebar DXF uses them
    import json
    spec = json.loads(p1["spec"].split("]", 1)[1])
    p2 = build_frame3d_payload("فرض‌ها را نشان بده", prior_spec=spec)
    assert p2["assumptions_command"] == "show" and "پوشش بتن: 50 mm" in "\n".join(p2["detailing_assumptions"])
    inp, raw, design = run_frame3d_for_export(p2["inputs"])
    doc, rows, _ = build_rebar_doc(inp, design)
    assert all(r.length_mm <= 10000 for r in rows)
    notes = " ".join(e.dxf.text for e in doc.modelspace().query("TEXT[layer=='NOTES']"))
    assert "Clear cover: 50 mm" in notes and "Top-bar cut-off: ln/4" in notes


def test_scwb_skip_and_ductility_override():
    p = build_frame3d_payload("special ductility, SCWB not applicable", prior_spec=dict(INPUTS))
    assert p["inputs"]["system"] == "RC_SMF" and p["design"]["ductility"] == "special"
    assert p["design"]["scwb_status"] == "NOT_APPLIED"


def test_assumption_prompt_routes_to_frame_agent():
    from app.application.agent_intent_routing import score_agent_intents
    top = max(score_agent_intents("پوشش ۵۰ میلی‌متر، قطع آرماتور در ln/4"), key=lambda m: m.score)
    assert top.agent_type.value == "ANALYSIS_AGENT"
