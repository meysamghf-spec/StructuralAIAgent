"""Downloadable outputs of a frame run: tables (xlsx/csv), figures, drawings, models, report, ZIP."""
import io
import zipfile

import pytest

from app.application import results_package as rp

INP = {"storeys": 2, "bays_x": 2, "bays_y": 1, "bay_x_m": 5, "bay_y_m": 4, "storey_height_m": 3.2, "seismic_code": "IRAN_2800"}


@pytest.fixture(scope="module")
def run():
    return rp.run(INP)


def test_tables_cover_all_result_groups(run):
    ts = rp.tables(*run)
    for k in ("joint_displacements", "reactions", "member_forces", "storey_drift", "modal", "base_shear",
              "design_beams", "design_columns", "foundation", "footings"):
        assert k in ts and ts[k][1], k
    h, rows = ts["member_forces"]
    assert h[6].startswith("N") and {r[0] for r in rows} >= {"D", "1.2D+1.6L"}
    assert len(ts["joint_displacements"][1]) % 3 == 0 or ts["joint_displacements"][1]


def test_combo_superposition(run):
    ts = rp.tables(*run)
    rows = {(r[0], r[1]): r for r in ts["reactions"][1]}
    nid = next(k[1] for k in rows)
    d, l, c = rows[("D", nid)], rows[("L", nid)], rows[("1.2D+1.6L", nid)]
    assert c[4] == pytest.approx(1.2 * d[4] + 1.6 * l[4], abs=0.05)


def test_xlsx_and_csv(run):
    from openpyxl import load_workbook
    ts = rp.tables(*run)
    wb = load_workbook(io.BytesIO(rp.tables_xlsx(ts)))
    assert set(wb.sheetnames) == {k[:31] for k in ts}
    csv = rp.table_csv(ts["storey_drift"]).decode("utf-8-sig")
    assert csv.splitlines()[0].startswith("direction")


@pytest.mark.parametrize("name", ["view3d", "deformed", "moment", "shear", "axial", "drift", "mode1"])
def test_figures_png(run, name):
    assert rp.figure(name, *run[:2], "png")[:8] == b"\x89PNG\r\n\x1a\n"


def test_figure_svg_and_unknown(run):
    assert b"<svg" in rp.figure("moment", *run[:2], "svg")[:500]
    with pytest.raises(KeyError):
        rp.figure("nope", *run[:2])


def test_single_items():
    assert rp.item("table", "all", "xlsx", INP)[0] == "frame-results.xlsx"
    assert rp.item("table", "reactions", "csv", INP)[2] == "text/csv"
    assert rp.item("model", "s2k", "", INP)[0] == "model.s2k"
    assert rp.item("drawing", "dxf_foundation", "pdf", INP)[1][:4] == b"%PDF"
    assert rp.item("report", "report_md", "", INP)[1]
    with pytest.raises(KeyError):
        rp.item("table", "optimization", "csv", INP)  # empty without an optimization result


def test_zip_contains_everything():
    got = []
    data, names = rp.build_zip(INP, on_file=lambda n, d: got.append(n))
    z = zipfile.ZipFile(io.BytesIO(data))
    assert "ERRORS.txt" not in z.namelist()
    for p in ("tables/frame-results.xlsx", "tables/csv/member_forces.csv", "figures/view3d.png", "figures/mode1.png",
              "models/model.e2k", "models/foundation.f2k", "models/model.s2k", "drawings/plans.dxf",
              "drawings/structural-set/structural-set.pdf", "report/report.md"):
        assert p in names, p
    assert got == ["frame-results.xlsx", "frame-results.zip"]


def test_optimization_table():
    opt = {"initial": {"objective": 10, "feasible": True}, "optimal": {"objective": 8, "feasible": True},
           "groups": [{"group": "C-S1", "section_cm": "35x35", "storeys": [1]}]}
    ts = rp.tables(*rp.run(INP), optimization=opt)
    assert [r[0] for r in ts["optimization"][1]] == ["initial", "optimal"]
    assert ts["optimization_groups"][1][0][0] == "C-S1"


def test_generic_frames():
    for s, bx, by in ((1, 1, 1), (4, 3, 2)):
        ts = rp.tables(*rp.run({**INP, "storeys": s, "bays_x": bx, "bays_y": by}))
        assert len({r[1] for r in ts["joint_displacements"][1]}) == (bx + 1) * (by + 1) * (s + 1)


def test_catalog():
    c = rp.catalog()
    assert "member_forces" in c["tables"] and "s2k" in c["models"] and "structural_set" in c["drawings"]
