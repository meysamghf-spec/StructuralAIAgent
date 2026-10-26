"""Phase 4: ETABS .e2k / SAFE .f2k / DXF text exports of the chat 3D frame (round-trip through our own parsers)."""

from __future__ import annotations

import math

import pytest

from app.application import csi_text_export as cte
from app.application import frame3d_chat_analysis as f3

PHASE1 = ("Analyze a 3-storey RC moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, columns 40x40 cm, "
          "beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, equivalent static seismic C=0.165 in X and Y.")
PHASE3 = ("Analyze and design per Mabhas 9 a 3-storey RC intermediate moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, "
          "columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, Standard 2800, "
          "high seismic hazard, soil type II, I=1.")


@pytest.fixture(scope="module")
def model():
    inp = f3.parse_frame3d_request(PHASE1)
    return inp, f3.run_frame3d(inp)


@pytest.fixture(scope="module")
def model2800():
    p = f3.build_frame3d_payload(PHASE3)
    return f3.run_frame3d_for_export({**p["inputs"], "_p": p["parsed_from_request"]})


def test_e2k_round_trip_geometry_and_assignments(model):
    inp, raw = model
    parsed = cte.parse_e2k(cte.build_e2k(inp, raw))
    assert parsed["story_elev"] == pytest.approx({"Base": 0.0, "Story1": 3.2, "Story2": 6.4, "Story3": 9.6})
    assert len(parsed["points"]) == 9 and parsed["points"]["9"] == (10.0, 10.0)
    members = cte.e2k_members_3d(parsed)
    cols = [m for m in members if m[1] == "COLUMN"]; beams = [m for m in members if m[1] == "BEAM"]
    assert (len(cols), len(beams)) == (raw["model"]["columns"], raw["model"]["beams"]) == (27, 36)
    # every analysed node position appears as a member end in the e2k model
    ends = {tuple(round(v, 6) for v in p) for m in members for p in m[2:]}
    want = {(x, y, round(z, 6)) for x in raw["geometry"]["XS"] for y in raw["geometry"]["YS"] for z in raw["geometry"]["Z"]}
    assert ends == want
    assert all(math.isclose(c[3][2] - c[2][2], 3.2) for c in cols)
    assert {s for _, _, s in parsed["line_assigns"]} == {"C40X40", "B30X45"}
    fs = parsed["frame_sections"]["B30X45"]
    assert fs[fs.index("D") + 1] == "0.45" and fs[fs.index("B") + 1] == "0.3"
    assert len(parsed["restraints"]) == 9 and len(parsed["diaph"]) == 27


def test_e2k_loads_combos_mass_and_seismic(model):
    inp, raw = model
    parsed = cte.parse_e2k(cte.build_e2k(inp, raw))
    assert parsed["load_patterns"] == ["Dead", "Live", "EX", "EY"]
    assert parsed["seismic"]["EX"] == {"C": 0.165, "k": 1.0, "dir": "X"}
    assert parsed["seismic"]["EY"]["dir"] == "Y"
    # total line load = beam gravity load used by the analysis (column weight comes from SELFWEIGHT 1 in ETABS)
    lengths = {n: 5.0 for n in parsed["lines"]}
    dead = sum(v * lengths[n] for n, _s, lc, v in parsed["line_loads"] if lc == "Dead")
    live = sum(v * lengths[n] for n, _s, lc, v in parsed["line_loads"] if lc == "Live")
    ncol = 27
    assert dead + ncol * raw["export"]["sw_col_kn"] == pytest.approx(raw["gravity_reaction_kn"]["D"], rel=1e-4)
    assert live == pytest.approx(raw["gravity_reaction_kn"]["L"], rel=1e-4)
    assert parsed["mass_source"] == {"Dead": 1.0, "Live": 0.2}
    assert len(parsed["combos"]) == len(raw["combos"]) == 10
    assert parsed["combos"]["COMB1"] == {"Dead": 1.4}
    assert {"Dead": 1.2, "Live": 1.0, "EX": -1.0} in parsed["combos"].values()


def test_e2k_uses_2800_coefficient_and_k(model2800):
    inp, raw, design = model2800
    parsed = cte.parse_e2k(cte.build_e2k(inp, raw, design))
    assert parsed["seismic"]["EX"]["C"] == pytest.approx(0.15, abs=1e-6)
    assert parsed["seismic"]["EX"]["k"] == pytest.approx(raw["seismic"]["k"], abs=1e-6)


def test_e2k_has_no_locale_commas_and_crlf(model):
    text = cte.build_e2k(*model)
    assert "\r\n" in text and text.rstrip().endswith("$ END OF MODEL FILE")
    for line in text.splitlines():
        if line.startswith("  POINT ") or "FVAL" in line:
            assert "," not in line


def test_f2k_point_loads_equal_column_reactions(model):
    inp, raw = model
    tables = cte.parse_f2k(cte.build_f2k(inp, raw))
    assert tables["PROGRAM CONTROL"][0]["CurrUnits"] == "KN, m, C"
    pts = [r for r in tables["OBJECT GEOMETRY - POINT COORDINATES"] if r["SpecialPt"] == "Yes"]
    assert len(pts) == 9
    loads = tables["LOAD ASSIGNMENTS - POINT LOADS"]
    dead = sum(float(r["Fgrav"]) for r in loads if r["LoadPat"] == "DEAD")
    assert dead == pytest.approx(raw["gravity_reaction_kn"]["D"], rel=1e-5)
    ex = sum(float(r["Fx"]) for r in loads if r["LoadPat"] == "EX")
    assert ex == pytest.approx(raw["base_shear"]["V_expected_kn"], rel=1e-4)  # loads on footing = applied shear
    combos = {r["Combo"] for r in tables["LOAD COMBINATIONS"]}
    assert "SERV1" in combos and "COMB2" in combos
    assert tables["SLAB PROPERTIES 01 - GENERAL"][0]["Slab"].startswith("FTG_H")  # footings replace the placeholder mat
    assert sum(a["Area"].startswith("FTG") for a in tables["OBJECT GEOMETRY - AREAS 01 - GENERAL"]) == 9


REQUIRED_F2K = ["PROGRAM CONTROL", "AUTOMATIC SLAB MESH OPTIONS", "GRID LINES", "MATERIAL PROPERTIES 01 - GENERAL",
                "MATERIAL PROPERTIES 03 - CONCRETE", "MATERIAL PROPERTIES 04 - REBAR", "SLAB PROPERTIES 01 - GENERAL",
                "SLAB PROPERTIES 02 - SOLID SLABS", "SOIL PROPERTIES", "OBJECT GEOMETRY - POINT COORDINATES",
                "OBJECT GEOMETRY - AREAS 01 - GENERAL", "SLAB PROPERTY ASSIGNMENTS", "SOIL PROPERTY ASSIGNMENTS", "LOAD PATTERNS",
                "LOAD CASES 01 - GENERAL", "LOAD CASES 02 - STATIC", "LOAD CASES 06 - LOADS APPLIED", "LOAD COMBINATIONS",
                "LOAD ASSIGNMENTS - POINT LOADS", "PUNCHING SHEAR DESIGN OVERWRITES 01 - GENERAL"]


def test_f2k_matches_safe_file_structure(model):
    inp, raw = model
    raw = {**raw, "foundation_design": None}  # mat case
    text = cte.build_f2k(inp, raw)
    assert text.endswith("END TABLE DATA\r\n") and "\n" not in text.replace("\r\n", "")
    text.encode("ascii")
    assert "BASIC MECHANICAL" not in text and "SAFE 2014" not in text
    t = cte.parse_f2k(text)
    for name in REQUIRED_F2K:
        assert t.get(name), name
    assert t["PROGRAM CONTROL"][0]["ProgramName"] == "SAFE 2016"
    conc = t["MATERIAL PROPERTIES 03 - CONCRETE"][0]
    assert float(conc["E"]) > 1e7 and float(conc["Fc"]) == 30000
    solid = {r["Slab"]: r for r in t["SLAB PROPERTIES 02 - SOLID SLABS"]}
    gen = {r["Slab"]: r for r in t["SLAB PROPERTIES 01 - GENERAL"]}
    assert set(solid) == set(gen) == {"MAT", "COLSTIFF"}
    assert solid["MAT"]["Type"] == "Mat" and float(solid["MAT"]["Thickness"]) >= 0.6 and solid["COLSTIFF"]["Type"] == "Stiff"
    assert "Thickness" not in gen["MAT"]
    defined = {r["Point"] for r in t["OBJECT GEOMETRY - POINT COORDINATES"]}
    areas = t["OBJECT GEOMETRY - AREAS 01 - GENERAL"]
    for a in areas:
        assert {a[f"Point{k}"] for k in range(1, int(a["NumPoints"]) + 1)} <= defined
    assert sum(a["Area"].startswith("STF") for a in areas) == 9 and any(a["Area"] == "MAT1" for a in areas)
    assert all(r["OpeningType"] == "None" for r in t["SLAB PROPERTY ASSIGNMENTS"])
    assert [r["Area"] for r in t["SOIL PROPERTY ASSIGNMENTS"]] == ["MAT1"] and float(t["SOIL PROPERTIES"][0]["Subgrade"]) > 0
    pats = {r["LoadPat"] for r in t["LOAD PATTERNS"]}
    assert pats == {"DEAD", "LIVE", "EX", "EY"}
    loads = t["LOAD ASSIGNMENTS - POINT LOADS"]
    for p in pats:
        assert len([r for r in loads if r["LoadPat"] == p]) == 9
    assert {r["LoadCase"] for r in t["LOAD CASES 02 - STATIC"]} == pats
    combos = {r["Combo"] for r in t["LOAD COMBINATIONS"]}
    assert all("+" not in c for c in combos) and {"SERV1", "COMB1"} <= combos
    assert {r["Load"] for r in t["LOAD COMBINATIONS"]} <= pats
    assert len(t["PUNCHING SHEAR DESIGN OVERWRITES 01 - GENERAL"]) == 9


def test_dxf_plans_and_3d(model2800):
    inp, raw, design = model2800
    plans = cte.parse_dxf_entities(cte.build_dxf_plans(inp, raw, design))
    assert sum(1 for e in plans if e["type"] == "POLYLINE" and e["8"] == "COLUMNS") == 27 + 9  # + 9 column outlines on the foundation plan
    assert sum(1 for e in plans if e["type"] == "LINE" and e["8"] == "BEAMS") == 36
    texts = [e["1"] for e in plans if e["type"] == "TEXT"]
    assert any(t.startswith("STORY 3 PLAN") for t in texts) and any("C40X40" in t for t in texts)
    assert any(e["8"] == "DESIGN_TEXT" for e in plans)  # Mabhas 9 rebar labels when designed
    frame = cte.parse_dxf_entities(cte.build_dxf_3d(inp, raw))
    lines = [e for e in frame if e["type"] == "LINE" and e.get("8") in ("FRAME_BEAMS", "FRAME_COLUMNS")]
    assert len(lines) == 63
    assert max(float(e["31"]) for e in lines) == pytest.approx(9600)
    assert sum(1 for e in frame if e["type"] == "POLYLINE" and e.get("8") == "FRAME_COLUMNS") == 9


@pytest.mark.parametrize("text,formats", [
    ("خروجی ایتبس بده", ["e2k"]),
    ("export to ETABS/SAFE/AutoCAD", ["e2k", "f2k", "dxf_plans", "dxf_3d"]),
    ("فایل سیف برای فونداسیون بده", ["f2k"]),
    ("خروجی اتوکد قاب را بده", ["dxf_plans", "dxf_3d"]),
    ("Analyze a 3-storey 3D frame, 2x2 bays", []),
])
def test_export_prompt_detection(text, formats):
    assert f3.requested_export_formats(text) == formats


def test_export_follow_up_uses_project_memory_spec():
    first = f3.build_frame3d_payload(PHASE1)
    memory = f3.frame3d_memory_summary(first)
    assert memory.startswith(f3.SPEC_TAG) and len(memory.split("\n")[0]) < 500
    spec = f3.prior_frame3d_spec({"memories": [{"content": "unrelated"}, {"content": memory[:500]}]})
    follow = f3.build_frame3d_payload("خروجی ایتبس و سیف بده", spec)
    assert follow["status"] == "completed" and follow["model_from_project_memory"] is True
    assert follow["export_requested"] == ["e2k", "f2k"]
    assert follow["results"]["column_max_P_kn"] == first["results"]["column_max_P_kn"]
    assert [e["format"] for e in follow["exports"] if e["requested"]] == ["e2k", "f2k"]
    assert "خروجی‌ها آماده" in f3.frame3d_markdown(follow)  # Persian prompt -> Persian reply
    none = f3.build_frame3d_payload("export to ETABS", None)
    assert none["status"] == "MISSING_REQUIRED_INPUT"
    assert f3.build_frame3d_payload("export this drawing to dxf", None) is None


def test_export_rejects_oversized_models():
    with pytest.raises(ValueError):
        f3.run_frame3d_for_export({"storeys": 30, "bays_x": 2, "bays_y": 2})


def test_export_endpoint_without_database():
    from fastapi.testclient import TestClient

    import app.main as main
    from app.api.deps import get_current_account

    application = getattr(main, "app", None) or main.create_app()
    application.dependency_overrides[get_current_account] = lambda: object()
    try:
        client = TestClient(application)
        inputs = {**f3.build_frame3d_payload(PHASE1)["inputs"]}
        for fmt, meta in cte.FORMATS.items():
            r = client.post("/api/v1/frame3d/export", json={"format": fmt, "inputs": inputs})
            assert r.status_code == 200, r.text
            assert f'filename="{meta["filename"]}"' in r.headers["content-disposition"]
        assert client.post("/api/v1/frame3d/export", json={"format": "pdf", "inputs": inputs}).status_code == 422
        assert client.post("/api/v1/frame3d/export", json={"format": "e2k", "inputs": {"storeys": 3}}).status_code == 422
    finally:
        application.dependency_overrides.clear()


def test_e2k_matches_etabs_file_structure(model):
    """Structure of a real ETABS-saved .e2k: '$ File ... saved', ordered sections, '  END' terminator."""
    inp, raw = model
    text = cte.build_e2k(inp, raw)
    text.encode("ascii")  # ASCII only, so no BOM / no UTF-8 multibyte
    assert not text.startswith("\ufeff")
    assert "\n" not in text.replace("\r\n", "")
    lines = text.split("\r\n")
    assert lines[0].startswith("$ File ") and " saved " in lines[0]
    assert lines[-3:] == ["  END", "$ END OF MODEL FILE", ""]
    heads = [l for l in lines if l.startswith("$ ")][1:]
    order = ["$ PROGRAM INFORMATION", "$ CONTROLS", "$ STORIES - IN SEQUENCE FROM TOP", "$ GRIDS", "$ MATERIAL PROPERTIES",
             "$ FRAME SECTIONS", "$ POINT COORDINATES", "$ LINE CONNECTIVITIES", "$ LINE ASSIGNS", "$ LOAD PATTERNS",
             "$ LOAD COMBINATIONS", "$ END OF MODEL FILE"]
    idx = [heads.index(h) for h in order]
    assert idx == sorted(idx)
    stories = [l.split('"')[1] for l in lines if l.startswith('  STORY "')]
    assert stories[-1] == "Base" and stories[0] == f"Story{inp.storeys}"
    assert all('GRADE "' in l for l in lines if ' TYPE "' in l and l.startswith("  MATERIAL"))
    assert "None" not in text


def test_e2k_strips_non_ascii_and_skips_undefined_cases(model):
    inp, raw = model
    raw = dict(raw); raw["base_shear"] = {}
    ex = dict(raw["export"]); ex["combo_factors"] = {"ترکیب ۱ D+Ex": {"D": 1.0, "Ex": 1.0}, **ex["combo_factors"]}
    raw["export"] = ex
    text = cte.build_e2k(inp, raw)
    text.encode("ascii")
    assert 'LOADCASE "EX"' not in text and "SHEARCOEFF" not in text
