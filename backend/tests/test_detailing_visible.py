"""Rebar detailing must work for a plain chat frame run (design_code NONE): the backend builds the Mabhas 9 design itself."""
from app.application import results_package as rp

BASE = {"storeys": 1, "bays_x": 1, "bays_y": 1, "bay_x_m": 5.0, "bay_y_m": 4.0, "storey_height_m": 3.2, "design_code": "NONE"}


def test_dxf_rebar_from_run_without_design():
    name, data, mime = rp.item("drawing", "dxf_rebar", "dxf", dict(BASE))
    text = data.decode("utf-8")
    assert name.endswith(".dxf") and "REBAR_MAIN" in text and "BAR BENDING SCHEDULE" in text


def test_design_required_set():
    assert {"dxf_rebar", "dxf_foundation", "structural_set"} <= rp.DESIGN_REQUIRED
