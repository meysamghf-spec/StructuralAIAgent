"""ETABS .e2k import: parser, engineer review step and analysis with SAIA's own solver."""

from pathlib import Path

import pytest

from app.application.model_import import ImportError_, analyze_imported_model, parse_model_file, review_summary
from app.application.model_import.analyze import apply_review

FIX = Path(__file__).parent / "fixtures" / "model_import"


def _load(name: str) -> dict:
    return parse_model_file(name, (FIX / name).read_bytes())


def _codes(m):
    return {i["code"] for i in m["issues"]}


def test_saia_export_round_trip_reads_everything():
    m = _load("saia_export_3storey.e2k")
    c = m["counts"]
    assert c["columns"] > 0 and c["beams"] > 0
    assert m["units"]["source"] == "KN, M"
    zs = sorted({n["z"] for n in m["nodes"].values()})
    assert zs[0] == 0 and abs(zs[-1] - 9.6) < 1e-6
    assert m["sections"]["C40X40"]["A"] == pytest.approx(0.16)
    assert m["sections"]["C40X40"]["modifiers"]["I33"] == 0.7
    assert m["materials"]["C30"]["E"] == pytest.approx(2.574296e7)
    assert all(len(f) == 6 and all(f) for f in m["supports"].values())
    assert "COMB1" in m["combos"] and m["combos"]["COMB1"]["Dead"] == 1.4
    s = review_summary(m)
    assert s["can_analyze"], s["issues"]
    res = analyze_imported_model(m)
    comb = res["cases"]["combo:COMB1"]
    # vertical equilibrium: base reaction = 1.4 x (self weight + dead line loads), computed independently
    sw = sum(m["sections"][x["section"]]["A"] * 25.0 * _len(m, x) for x in m["members"])
    lines = sum(-ld["wz"] * _len(m, _mem(m, ld["member"])) for ld in m["member_loads"] if ld["pattern"] == "Dead")
    assert comb["base_reaction_kN"][2] == pytest.approx(1.4 * (sw + lines), rel=1e-6)


def _mem(m, mid):
    return next(x for x in m["members"] if x["id"] == mid)


def _len(m, mem):
    a, b = m["nodes"][mem["i"]], m["nodes"][mem["j"]]
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2) ** 0.5


def test_units_story_and_issue_listing():
    m = _load("portal_kgf_cm.e2k")
    assert m["units"]["source"] == "KGF, CM"
    assert {n["z"] for n in m["nodes"].values()} == {0.0, 3.5, 6.5}
    c40 = m["sections"]["C40"]
    assert c40["A"] == pytest.approx(0.16) and c40["I33"] == pytest.approx(0.4 ** 4 / 12)
    assert m["materials"]["C25"]["E"] == pytest.approx(250000 * 9.80665e-3 / 1e-4)
    assert m["materials"]["C25"]["unit_weight"] == pytest.approx(0.0025 * 9.80665e-3 / 1e-6)
    assert m["counts"]["columns"] == 4 and m["counts"]["beams"] == 2 and m["counts"]["braces"] == 1
    assert m["supports"]["2@Base"] == [True, True, True, False, False, False]
    ld = next(x for x in m["member_loads"] if x["pattern"] == "Dead")
    assert ld["wz"] == pytest.approx(-20 * 9.80665e-3 / 1e-2)
    live = [x for x in m["member_loads"] if x["pattern"] == "Live"]
    assert len(live) == 8  # trapezoid kept as 8 piecewise-uniform steps
    assert sum(x["wz"] * (x["rb"] - x["ra"]) for x in live) == pytest.approx(-10 * 9.80665e-3 / 1e-2)
    assert live[0]["wz"] > live[-1]["wz"]  # 5 -> 15 increasing (more negative)
    b1 = next(x for x in m["members"] if x["id"] == "B1@Story1")
    assert b1["rel_i"] == [False, False, False, False, True, True] and not any(b1["rel_j"])
    assert m["sections"]["IPE300"]["catalog"].startswith("IPE300")
    eq = m["nodal_loads"][0]
    assert eq["node"] == "1@Story2" and eq["fx"] == pytest.approx(9.80665)
    assert m["combos"]["ENV"] == {"Dead": 1.2, "Live": 1.6}
    codes = _codes(m)
    assert {"catalog", "combo_type", "combo_case", "auto_lateral"} <= codes
    assert not {"release", "areas", "trapezoid", "diaphragm", "section_shape"} & codes
    s = review_summary(m)
    assert s["can_analyze"] and s["blocking"] == 0


def test_review_edits_unblock_and_analysis_matches_hand_calc():
    m = _load("portal_kgf_cm.e2k")
    m2 = apply_review(m, {"sections": {"IPE300": {"A": 53.8e-4, "I33": 8356e-8, "I22": 604e-8, "J": 20.1e-8}},
                          "beam_line_loads": [{"pattern": "Live", "w": 5, "story": "Story2"}],
                          "confirmed": ["catalog:IPE300"]})
    s = review_summary(m2)
    assert s["can_analyze"]
    assert any(i.get("confirmed") for i in m2["issues"])
    res = analyze_imported_model(m2)
    # total vertical reaction under Live = trapezoid avg on B1@Story1 (5 m) + 5 kN/m added on B1@Story2
    live = res["cases"]["pattern:Live"]["base_reaction_kN"][2]
    assert live == pytest.approx(10 * 9.80665e-3 / 1e-2 * 5 + 5 * 5, rel=1e-6)
    eqx = res["cases"]["pattern:EQX"]["base_reaction_kN"][0]
    assert eqx == pytest.approx(-9.80665, rel=1e-6)


def test_cantilever_tip_deflection_equals_PL3_over_3EI():
    txt = """$ CONTROLS
  UNITS "KN" "M" "C"
$ STORIES - IN SEQUENCE FROM TOP
  STORY "S1" HEIGHT 4
  STORY "Base" ELEV 0
$ MATERIAL PROPERTIES
  MATERIAL "C" TYPE "Concrete" WEIGHTPERVOLUME 0
  MATERIAL "C" SYMTYPE "Isotropic" E 30000000 U 0.2
$ FRAME SECTIONS
  FRAMESECTION "C" MATERIAL "C" SHAPE "Concrete Rectangular" D 0.5 B 0.5
$ POINT COORDINATES
  POINT "1" 0 0
$ LINE CONNECTIVITIES
  LINE "C1" COLUMN "1" "1" 1
$ POINT ASSIGNS
  POINTASSIGN "1" "Base" RESTRAINT "UX UY UZ RX RY RZ"
$ LINE ASSIGNS
  LINEASSIGN "C1" "S1" SECTION "C"
$ LOAD PATTERNS
  LOADPATTERN "P" TYPE "Other" SELFWEIGHT 0
$ POINT OBJECT LOADS
  POINTLOAD "1" "S1" TYPE "FORCE" LC "P" FX 10
"""
    m = parse_model_file("c.e2k", txt.encode())
    res = analyze_imported_model(m)
    d = res["cases"]["pattern:P"]["max_displacement_m"]
    assert d == pytest.approx(10 * 4 ** 3 / (3 * 3e7 * 0.5 ** 4 / 12), rel=1e-6)
    assert res["cases"]["pattern:P"]["members"]["C1@S1"]["M"] == pytest.approx(40, rel=1e-6)


@pytest.mark.parametrize("name,code", [("a.dwg", "dwg"), ("a.txt", "ext")])
def test_rejected_files(name, code):
    with pytest.raises(ImportError_) as e:
        parse_model_file(name, b"x")
    assert e.value.code == code and e.value.fa


def test_empty_file():
    with pytest.raises(ImportError_):
        parse_model_file("a.e2k", b"")


# ---------------------------------------------------------------- API (parse -> review -> analyze -> latest)
def _auth(api_client):
    import uuid
    r = api_client.post("/api/v1/auth/register", json={"email": f"imp-{uuid.uuid4().hex}@example.com", "password": "secure-password"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    pid = api_client.post("/api/v1/projects", json={"name": "Import"}, headers=h).json()["project"]["id"]
    return h, pid


def test_api_flow_review_gates_analysis(api_client):
    h, pid = _auth(api_client)
    data = (FIX / "portal_kgf_cm.e2k").read_bytes()
    r = api_client.post("/api/v1/model-import/parse", files={"file": ("portal.e2k", data)}, data={"project_id": pid}, headers=h)
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["review"]["blocking"] == 1 and st["state_file_id"]
    r = api_client.post("/api/v1/model-import/analyze", json={"model": st["model"], "project_id": pid}, headers=h)
    assert r.status_code == 409
    r = api_client.post("/api/v1/model-import/review", headers=h, json={"model": st["model"], "project_id": pid, "edits": {
        "sections": {"IPE300": {"A": 53.8e-4, "I33": 8356e-8, "I22": 604e-8, "J": 20.1e-8}}}})
    st = r.json()
    assert st["review"]["can_analyze"] and st["review"]["requires_confirmation"]
    r = api_client.post("/api/v1/model-import/analyze", json={"model": st["model"], "project_id": pid}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["unconfirmed"]
    r = api_client.post("/api/v1/model-import/review", headers=h, json={"model": st["model"], "project_id": pid, "edits": {
        "confirmed": st["review"]["requires_confirmation"]}})
    st = r.json()
    r = api_client.post("/api/v1/model-import/analyze", json={"model": st["model"], "project_id": pid}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["analysis"]["cases"]["combo:ULS1"]["base_reaction_kN"][2] > 0
    latest = api_client.get(f"/api/v1/model-import/latest?project_id={pid}", headers=h).json()["state"]
    assert latest["stage"] == "analyzed"


def test_api_dwg_message(api_client):
    h, _ = _auth(api_client)
    r = api_client.post("/api/v1/model-import/parse", files={"file": ("a.dwg", b"AC1032")}, headers=h)
    assert r.status_code == 422 and "DXF" in r.json()["detail"]["en"]
