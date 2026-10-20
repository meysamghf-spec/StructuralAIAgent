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
