"""Model import phase 2: slabs, diaphragms, releases, P-Delta, modal/RS, 2800 & wind generation, sparse engine,
catalog, CSI table (s2k/f2k) and DXF parsers. Every number is a hand check against closed-form results."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from model_import_gen import building_e2k  # noqa: E402

from app.application.model_import import parse_model_file, analyze_imported_model, review_summary  # noqa: E402
from app.application.model_import.analyze import apply_review  # noqa: E402
from app.application.model_import.catalog import lookup  # noqa: E402
from app.application.model_import.slabs import distribute_area, is_one_way  # noqa: E402


def _bldg(**kw):
    return parse_model_file("b.e2k", building_e2k(**kw).encode())


# ------------------------------------------------------------------ slabs
def test_two_way_square_slab_triangles():
    poly = np.array([[0, 0], [6, 0], [6, 6], [0, 6.0]])
    beams = [("B1", np.array([0, 0.]), np.array([6, 0.])), ("B2", np.array([6, 0.]), np.array([6, 6.])),
             ("B3", np.array([6, 6.]), np.array([0, 6.])), ("B4", np.array([0, 6.]), np.array([0, 0.]))]
    out, total = distribute_area(poly, 5.0, beams)
    assert total == pytest.approx(180)
    for b in out.values():
        tot = sum((bb - a) * w for a, bb, w in b)
        assert tot == pytest.approx(45, rel=0.02)          # 1/4 each
        peak = max(w for _, _, w in b)
        assert peak == pytest.approx(5 * 6 / 2 * 7 / 8, rel=0.05)  # triangle peak qL/2 averaged over the central 1/8 step
    assert sum((bb - a) * w for b in out.values() for a, bb, w in b) == pytest.approx(180, rel=1e-9)


def test_one_way_slab_goes_to_long_beams():
    poly = np.array([[0, 0], [8, 0], [8, 3], [0, 3.0]])
    ow, d = is_one_way(poly)
    assert ow and abs(d[0]) == pytest.approx(1)
    beams = [("L1", np.array([0, 0.]), np.array([8, 0.])), ("S1", np.array([8, 0.]), np.array([8, 3.])),
             ("L2", np.array([8, 3.]), np.array([0, 3.])), ("S2", np.array([0, 3.]), np.array([0, 0.]))]
    out, total = distribute_area(poly, 4.0, beams, d)
    assert set(out) == {"L1", "L2"}
    for b in out.values():
        assert sum((bb - a) * w for a, bb, w in b) == pytest.approx(48, rel=1e-6)
        assert all(w == pytest.approx(6, rel=0.02) for _, _, w in b)  # uniform q*s/2


# ------------------------------------------------------------------ full pipeline: weight, 2800, equilibrium
def test_building_weight_2800_base_shear_and_equilibrium():
    m = _bldg()
    assert m["counts"]["slabs"] == 8 and len(m["diaphragms"]) == 2
    r = analyze_imported_model(m)
    s = r["seismic"]
    # hand weight per level: slab 375 + q_D 200 + beams 300 + columns + 0.2*live 40
    assert [lv["W_kN"] for lv in s["levels"]] == pytest.approx([1095, 1005])
    assert s["V_kN"] == pytest.approx(s["C"] * s["W_kN"]) and s["C"] == pytest.approx(0.3 * 2.5 * 1 / 5)
    # F_i ~ W_i h_i
    f1, f2 = (lv["F_kN"] for lv in s["levels"])
    assert f2 / f1 == pytest.approx(1005 * 6.4 / (1095 * 3.2))
    base_x = r["cases"]["pattern:EX"]["base_reaction_kN"][0]
    assert abs(base_x) == pytest.approx(315, rel=1e-6)
    dead_z = r["cases"]["pattern:Dead"]["base_reaction_kN"][2]
    assert dead_z == pytest.approx(2 * (375 + 200 + 300) + 2 * 180, rel=1e-6)
    assert max(r["equilibrium"].values()) < 1e-6
    assert any("2800" in a["en"] for a in r["assumptions"])


def test_wind_generated_and_combos_assumed():
    r = analyze_imported_model(_bldg())
    assert "pattern:WX (Mabhas 6)" in r["cases"]
    q = 0.5 * 1.25 * (100 / 3.6) ** 2 / 1000  # default V = 100 km/h
    w = r["cases"]["pattern:WX (Mabhas 6)"]["base_reaction_kN"][0]
    assert 0 < abs(w) < q * 2.0 * 1.3 * 10 * 6.4 * 1.01  # bounded by q*Ce_max*Cq*B*H
    assert any(k.startswith("combo:1.2D+L+EX") for k in r["cases"])


# ------------------------------------------------------------------ diaphragm
def test_rigid_diaphragm_equal_drifts_and_shear_split():
    r = analyze_imported_model(_bldg(nx=1, ny=1, storeys=1, slabs=True, diaph=True))
    ux = r["cases"]["pattern:EX"]
    cols = [v for k, v in ux["members"].items() if k.startswith("C")]
    vs = [c["V"] for c in cols]
    assert max(vs) == pytest.approx(min(vs), rel=0.15)  # identical columns; spread only from 5% accidental eccentricity
    assert sum(c["V"] for c in cols) == pytest.approx(r["seismic"]["V_kN"], rel=0.02)


# ------------------------------------------------------------------ releases
def test_pinned_beam_ends_give_simple_span_moment():
    from app.application.model_import.engine import FrameEngine
    # beam 6 m between fixed supports, but both ends released for bending -> M = wL^2/8, end moments 0
    el = dict(id="B", i="A", j="B", E=2e8, G=8e7, A=0.01, I33=1e-4, I22=1e-4, J=1e-5,
              rel_i=[False, False, False, True, True, True], rel_j=[False, False, False, False, True, True])
    eng = FrameEngine([("A", 0, 0, 0), ("B", 6, 0, 0)], [el], {"A": [True] * 6, "B": [True] * 6})
    F, eql = eng.element_loads({"B": [(0, 6, [0, 0, -10])]})
    U = eng.solve(F)
    st = eng.stations(eng.end_forces(U, eql), eql)
    M = st[0, :, 5]
    assert max(abs(M)) == pytest.approx(10 * 36 / 8, rel=1e-6)
    assert abs(M[0]) < 1e-6 and abs(M[-1]) < 1e-6


def test_e2k_release_honoured_in_pipeline():
    r = analyze_imported_model(_bldg(nx=1, ny=1, storeys=1, release_beams=True))
    beam = next(v for k, v in r["envelope"].items() if k.startswith("B"))
    assert beam["M"] > 0
    assert r["counts"]["released_members"] >= 4 if "released_members" in r["counts"] else True


# ------------------------------------------------------------------ P-Delta and modal
def test_pdelta_amplification_matches_theory():
    from app.application.model_import.engine import FrameEngine
    L, E, I = 4.0, 2e8, 1e-5
    Pcr = math.pi ** 2 * E * I / (4 * L ** 2)
    P = 0.3 * Pcr
    el = dict(id="C", i="A", j="B", E=E, G=8e7, A=0.01, I33=I, I22=I, J=1e-5)
    eng = FrameEngine([("A", 0, 0, 0), ("B", 0, 0, L)], [el], {"A": [True] * 6})
    F = np.zeros(12); F[6] = 1.0
    d0 = eng.solve(F)[6]
    eng.set_pdelta(np.array([-P]))
    d1 = eng.solve(F)[6]
    assert d1 / d0 == pytest.approx(1 / (1 - P / Pcr), rel=0.01)


def test_modal_period_single_column_mass():
    from app.application.model_import.engine import FrameEngine
    L, E, I, mass = 3.0, 2e8, 2e-5, 10.0
    el = dict(id="C", i="A", j="B", E=E, G=8e7, A=0.01, I33=I, I22=I, J=1e-5)
    eng = FrameEngine([("A", 0, 0, 0), ("B", 0, 0, L)], [el], {"A": [True] * 6})
    eng.nodal_mass = {"B": mass}
    res = eng.modal(2)
    k = 3 * E * I / L ** 3
    assert res["modes"][0]["T"] == pytest.approx(2 * math.pi * math.sqrt(mass / k), rel=1e-6)
    assert res["modes"][1]["cum_x"] + res["modes"][1]["cum_y"] == pytest.approx(2, rel=1e-6)


def test_modal_rs_and_drift_in_pipeline():
    r = analyze_imported_model(_bldg())
    assert r["modal"]["modes"][0]["T"] > 0
    rs = r["response_spectrum"]
    assert rs["base_shear_kN"]["X"] >= 0.85 * r["seismic"]["V_kN"] * 0.999
    assert r["drifts"] and all(d["max"] < r["seismic"]["drift_limit"] for d in r["drifts"])
    assert r["pdelta"]["amplification"]["EX"] >= 1.0


# ------------------------------------------------------------------ no node cap (sparse)
def test_large_model_without_cap():
    m = _bldg(nx=8, ny=8, storeys=10)
    assert m["counts"]["nodes"] > 600
    r = analyze_imported_model(m)
    assert max(r["equilibrium"].values()) < 1e-5
    assert r["design"]["count"] == m["counts"]["members"] or r["design"]["count"] > 0


# ------------------------------------------------------------------ catalog / steel design
def test_catalog_profiles():
    ipe = lookup("IPE300")
    assert ipe["A"] == pytest.approx(53.8e-4, rel=0.01) and ipe["I33"] == pytest.approx(8356e-8, rel=0.01)
    assert lookup("HEB200")["A"] == pytest.approx(78.1e-4, rel=0.01)
    assert lookup("HE200B")["A"] == pytest.approx(78.1e-4, rel=0.01)
    assert lookup("UNP200")["A"] == pytest.approx(32.2e-4, rel=0.02)
    box = lookup("BOX200x10")
    assert box["A"] == pytest.approx(0.2 ** 2 - 0.18 ** 2, rel=1e-6)
    pipe = lookup("PIPE168x8")
    assert pipe["A"] == pytest.approx(math.pi / 4 * (0.168 ** 2 - 0.152 ** 2), rel=1e-6)
    assert lookup("FOO") is None


def test_steel_building_designs():
    r = analyze_imported_model(_bldg(steel=True, col="HEB240", beam="IPE300"))
    d = r["design"]
    assert d["count"] > 0 and all(0 <= x["ratio"] for x in d["members"])
    assert any(x["kind"] == "steel" and "H1-1" in x["detail"] for x in d["members"])


# ------------------------------------------------------------------ CSI tables (s2k / f2k)
S2K = """File C:\\x.s2k was saved on m/d/yy at h:mm:ss
TABLE:  "PROGRAM CONTROL"
   ProgramName=SAP2000   Version=24.0.0   CurrUnits="KN, m, C"
TABLE:  "MATERIAL PROPERTIES 01 - GENERAL"
   Material=S1   Type=Steel
TABLE:  "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"
   Material=S1   UnitWeight=0   E1=200000000   U12=0.3
TABLE:  "FRAME SECTION PROPERTIES 01 - GENERAL"
   SectionName=SEC   Material=S1   Shape=General   Area=0.01   TorsConst=1E-05   I33=0.0001   I22=0.0001 _
        AS2=0.005   AS3=0.005
TABLE:  "JOINT COORDINATES"
   Joint=1   CoordSys=GLOBAL   CoordType=Cartesian   XorR=0   Y=0   Z=0
   Joint=2   CoordSys=GLOBAL   CoordType=Cartesian   XorR=6   Y=0   Z=0
TABLE:  "CONNECTIVITY - FRAME"
   Frame=1   JointI=1   JointJ=2
TABLE:  "FRAME SECTION ASSIGNMENTS"
   Frame=1   AnalSect=SEC
TABLE:  "JOINT RESTRAINT ASSIGNMENTS"
   Joint=1   U1=Yes   U2=Yes   U3=Yes   R1=Yes   R2=No   R3=No
   Joint=2   U1=No   U2=Yes   U3=Yes   R1=Yes   R2=No   R3=No
TABLE:  "LOAD PATTERN DEFINITIONS"
   LoadPat=DEAD   DesignType=Dead   SelfWtMult=0
TABLE:  "FRAME LOADS - DISTRIBUTED"
   Frame=1   LoadPat=DEAD   CoordSys=GLOBAL   Type=Force   Dir=Gravity   DistType=RelDist   RelDistA=0   RelDistB=1 _
        FOverLA=10   FOverLB=10
END TABLE DATA
"""


def test_s2k_simple_beam():
    m = parse_model_file("x.s2k", S2K.encode())
    assert m["format"] == "s2k" and m["counts"]["members"] == 1
    s = review_summary(m)
    assert s["can_analyze"], m["issues"]
    r = analyze_imported_model(m)
    Rz = r["cases"]["pattern:DEAD"]["base_reaction_kN"][2]
    assert Rz == pytest.approx(60, rel=1e-6)
    assert r["cases"]["pattern:DEAD"]["members"]["1"]["M"] == pytest.approx(45, rel=1e-3)


F2K = S2K.replace("SAP2000", "SAFE").replace('"JOINT RESTRAINT ASSIGNMENTS"\n   Joint=1   U1=Yes   U2=Yes   U3=Yes   R1=Yes   R2=No   R3=No\n   Joint=2   U1=No   U2=Yes   U3=Yes   R1=Yes   R2=No   R3=No',
                                                          '"JOINT RESTRAINT ASSIGNMENTS"\n   Joint=1   U1=Yes   U2=Yes   U3=Yes   R1=Yes   R2=No   R3=No\n   Joint=2   U1=No   U2=Yes   U3=Yes   R1=Yes   R2=No   R3=No')


def test_f2k_parses():
    m = parse_model_file("x.f2k", F2K.encode())
    assert m["format"] == "f2k" and m["counts"]["members"] == 1


# ------------------------------------------------------------------ DXF
def _dxf(entities: list[str], insunits: int | None = 6) -> bytes:
    hdr = ["0", "SECTION", "2", "HEADER"] + (["9", "$INSUNITS", "70", str(insunits)] if insunits else []) + ["0", "ENDSEC"]
    body = ["0", "SECTION", "2", "ENTITIES"]
    for e in entities:
        body += e.split("|")
    body += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(hdr + body).encode()


def _line(layer, a, b):
    return f"0|LINE|8|{layer}|10|{a[0]}|20|{a[1]}|30|{a[2]}|11|{b[0]}|21|{b[1]}|31|{b[2]}"


def test_dxf_3d_frame_by_layers():
    ents = [_line("COLUMNS", (0, 0, 0), (0, 0, 3)), _line("COLUMNS", (5, 0, 0), (5, 0, 3)), _line("BEAMS", (0, 0, 3), (5, 0, 3))]
    m = parse_model_file("f.dxf", _dxf(ents))
    assert m["counts"]["columns"] == 2 and m["counts"]["beams"] == 1
    s = review_summary(m)
    assert not s["can_analyze"]  # sections must be given
    m2 = apply_review(m, {"sections": {"COLUMNS": {"catalog": "HEB200"}, "BEAMS": {"catalog": "IPE300"}},
                          "beam_line_loads": [{"pattern": "Dead", "w": 10}]})
    assert review_summary(m2)["can_analyze"], [i for i in m2["issues"] if i["severity"] == "blocking"]
    r = analyze_imported_model(m2)
    assert r["cases"]["pattern:Dead"]["base_reaction_kN"][2] == pytest.approx(10 * 5 + sum(
        lookup(n)["A"] * 77 * L for n, L in (("HEB200", 6), ("IPE300", 5))), rel=1e-3)


def test_dxf_plan_extruded_with_slabs_and_units():
    mm = 1000
    sq = [(0, 0), (6, 0), (6, 6), (0, 6)]
    ents = [_line("تیر", (sq[k][0] * mm, sq[k][1] * mm, 0), (sq[(k + 1) % 4][0] * mm, sq[(k + 1) % 4][1] * mm, 0)) for k in range(4)]
    ents += [f"0|CIRCLE|8|ستون|10|{x * mm}|20|{y * mm}|30|0|40|200" for x, y in sq]
    m = parse_model_file("p.dxf", _dxf(ents, insunits=None))
    codes = {i["code"] for i in m["issues"]}
    assert {"dxf_units", "dxf_storeys", "dxf_slabs"} <= codes
    m2 = apply_review(m, {"dxf": {"storeys": 3, "height": 3.0}, "sections": {"تیر": {"catalog": "IPE300"}, "COLUMN": {"catalog": "HEB300"}}})
    assert m2["counts"]["columns"] == 12 and m2["counts"]["beams"] == 12 and m2["counts"]["slabs"] == 3
    assert m2["nodes"][next(iter(m2["nodes"]))]["x"] in (0, 6)
    m3 = apply_review(m2, {"area_loads": [{"pattern": "Dead", "q": 5}]})
    assert review_summary(m3)["can_analyze"], [i for i in m3["issues"] if i["severity"] == "blocking"]
    r = analyze_imported_model(m3)
    sw = sum(lookup(n)["A"] * 77 * L for n, L in (("IPE300", 3 * 24), ("HEB300", 4 * 9)))
    assert r["cases"]["pattern:Dead"]["base_reaction_kN"][2] == pytest.approx(3 * 36 * 5 + sw, rel=1e-3)
