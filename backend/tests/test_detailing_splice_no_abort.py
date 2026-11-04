"""Regression: 'Rebar details (DXF)' aborted with 'no permitted lap-splice location within one stock length'
on long-span frames (e.g. 13 m bays: midspan-to-midspan > one 12 m stock bar). The build must never abort:
splices go to the permitted zones, else the least-bad zone / a mechanical coupler with a warning on R-03."""
import io

from app.application import rebar_detailing as rd
from app.application import results_package as rp

LONG = {"soil": "II", "zone": "HIGH", "bays_x": 4, "bays_y": 3, "fc_mpa": 30.0, "fy_mpa": 400.0, "system": "RC_IMF",
        "bay_x_m": 13.0, "bay_y_m": 8.0, "storeys": 6, "seismic_code": "IRAN_2800", "storey_height_m": 3.2}


def _pieces_ok(pieces, total, limit):
    assert pieces[0][0] == 0 and pieces[-1][1] == total
    assert all(e - a <= limit + 1e-6 for a, e in pieces)
    assert all(b[0] <= a[1] for a, b in zip(pieces, pieces[1:]))  # laps overlap or couplers butt


def test_old_points_fail_but_zones_succeed():
    # one centre per 13 m span: the old algorithm found no point within 12 m after the first splice
    total, lap, centers = 52000, 900, [6500 + 13000 * k for k in range(4)]
    zones = [(13000 * k + 4000, 13000 * k + 9000) for k in range(4)]
    w: list[str] = []
    p = rd.split_bar(total, lap, centers, 11700, zones=zones, warnings=w, label="B")
    _pieces_ok(p, total, 11700)
    assert not w


def test_least_bad_zone_with_warning():
    w: list[str] = []
    p = rd.split_bar(40000, 900, [20000], 11700, warnings=w, label="B-X1", avoid=[(0, 3000)])
    _pieces_ok(p, 40000, 11700)
    assert w and "least-bad" in w[0] and "B-X1" in w[0]


def test_mechanical_coupler_when_stock_too_short():
    w: list[str] = []
    p = rd.split_bar(20000, 3000, [], 5000, warnings=w, label="B")
    _pieces_ok(p, 20000, 5000)
    assert any("coupler" in s for s in w)


def test_long_span_frame_rebar_dxf_builds():
    name, data, _ = rp.item("drawing", "dxf_rebar", "dxf", {**LONG, "design_code": "MABHAS9"})
    assert data and name.endswith(".dxf")


def test_short_stock_length_reports_splice_warnings_on_schedule():
    inp, raw, design = rp.run({**LONG, "design_code": "MABHAS9"})
    inp.assumptions = {**(getattr(inp, "assumptions", None) or {}), "stock_length_m": 6}
    doc, rows, _ = rd.build_rebar_doc(inp, design)
    buf = io.StringIO(); doc.write(buf)
    assert rows
    assert isinstance(doc.splice_warnings, list)
    if doc.splice_warnings:
        assert "SPLICE WARNINGS" in buf.getvalue()
