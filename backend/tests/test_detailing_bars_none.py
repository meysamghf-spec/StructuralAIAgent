"""Regression: Detailing downloads failed with 'cannot read bars None' when a Mabhas 9 group had no bar
arrangement (e.g. 4-storey 3x3 frame, high zone, default 300x450 beams: 'Required bars do not fit in one layer')."""
from app.application import rebar_detailing as rd
from app.application import results_package as rp

FRAME = {"soil": "II", "zone": "HIGH", "bays_x": 3, "bays_y": 3, "fc_mpa": 30.0, "fy_mpa": 400.0, "system": "RC_IMF",
         "bay_x_m": 5.0, "bay_y_m": 5.0, "storeys": 4, "seismic_code": "IRAN_2800", "storey_height_m": 3.2}


def test_project_frame_has_groups_without_bars_and_rebar_dxf_builds():
    inp, raw, design = rp.run({**FRAME, "design_code": "MABHAS9"})
    # pt616u: NG groups (formerly top_bars None, the condition that crashed) now carry the max one-layer fill from design
    ng = [g for g in design["beams"] if g.get("rebar_basis") == "MAX_FEASIBLE"]
    assert ng and all(g.get("top_bars") and g.get("stirrups") for g in ng)
    name, data, _ = rp.item("drawing", "dxf_rebar", "dxf", FRAME)
    assert data and name.endswith(".dxf")
    assert b"NG" in data


def test_complete_design_fills_missing_bars_with_warnings():
    inp, raw, design = rp.run({**FRAME, "design_code": "MABHAS9"})
    design["columns"][0] = {**design["columns"][0], "bars": None, "ties": None, "notes": ["No bar arrangement fits"]}
    full, warnings = rd.complete_design(inp, design)
    for g in full["beams"]:
        rd.parse_bars(g["top_bars"]); rd.parse_bars(g["bottom_bars"]); rd.parse_spacing(g["stirrups"])
    for g in full["columns"]:
        rd.parse_bars(g["bars"]); rd.parse_spacing(g["ties"])
    assert warnings and any(w.startswith("C-") for w in warnings)
    assert "هشدار" in rd.detailing_warning_fa(warnings)
    assert design["columns"][0]["bars"] is None  # input design is not mutated
    rd.build_dxf_rebar(inp, raw, design)


def test_structural_set_column_without_bars():
    from app.application.autocad import structural_set as ss
    inp, raw, design = rp.run({**FRAME, "design_code": "MABHAS9"})
    design["columns"][0] = {**design["columns"][0], "bars": None, "ties": None}
    sheets, _ = ss.build_structural_set(inp, raw, design, None)
    assert sheets
