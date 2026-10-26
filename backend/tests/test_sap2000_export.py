"""SAP2000 .s2k export of the chat 3D frame: parse sanity, table names, counts match the model."""

from __future__ import annotations

import pytest

from app.application import csi_text_export as cte
from app.application import frame3d_chat_analysis as f3
from app.application.sap2000_export import build_s2k, parse_s2k

REQ = ("Analyze a 4-storey RC moment frame, 3 bays of 5 m in X and 2 bays of 4 m in Y, storey height 3.2 m, columns 40x40 cm, "
       "beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, equivalent static seismic C=0.165 in X and Y.")

INPUTS = {"storeys": 4, "bays_x": 3, "bays_y": 2, "bay_x_m": 5.0, "bay_y_m": 4.0, "storey_height_m": 3.2,
          "fc_mpa": 30, "fy_mpa": 400, "dead_kn_m2": 6, "live_kn_m2": 2, "seismic_c": 0.165}

TABLES = {"PROGRAM CONTROL", "MATERIAL PROPERTIES 01 - GENERAL", "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES",
          "FRAME SECTION PROPERTIES 01 - GENERAL", "JOINT COORDINATES", "CONNECTIVITY - FRAME", "FRAME SECTION ASSIGNMENTS",
          "JOINT RESTRAINT ASSIGNMENTS", "CONSTRAINT DEFINITIONS - DIAPHRAGM", "JOINT CONSTRAINT ASSIGNMENTS",
          "LOAD PATTERN DEFINITIONS", "LOAD CASE DEFINITIONS", "CASE - STATIC 1 - LOAD ASSIGNMENTS", "CASE - MODAL 1 - GENERAL",
          "FRAME LOADS - DISTRIBUTED", "COMBINATION DEFINITIONS", "AUTO SEISMIC - USER COEFFICIENT", "MASS SOURCE"}


@pytest.fixture(scope="module")
def model():
    inp = f3.inputs_from_dict(INPUTS)
    raw = f3.run_frame3d(inp)
    text = build_s2k(inp, raw)
    return inp, raw, text, parse_s2k(text)


def test_tables_and_units(model):
    _inp, _raw, text, t = model
    assert TABLES <= set(t)
    assert text.rstrip().endswith("END TABLE DATA")
    pc = t["PROGRAM CONTROL"][0]
    assert pc["ProgramName"] == "SAP2000" and pc["CurrUnits"] == "KN, m, C"


def test_counts_match_model(model):
    inp, raw, _text, t = model
    nj = (inp.bays_x + 1) * (inp.bays_y + 1)
    assert len(t["JOINT COORDINATES"]) == nj * (inp.storeys + 1) == 60
    assert len(t["CONNECTIVITY - FRAME"]) == raw["model"]["columns"] + raw["model"]["beams"]
    assert len(t["FRAME SECTION ASSIGNMENTS"]) == len(t["CONNECTIVITY - FRAME"])
    assert len(t["JOINT RESTRAINT ASSIGNMENTS"]) == nj
    assert len(t["CONSTRAINT DEFINITIONS - DIAPHRAGM"]) == inp.storeys
    assert len(t["JOINT CONSTRAINT ASSIGNMENTS"]) == nj * inp.storeys
    joints = {r["Joint"] for r in t["JOINT COORDINATES"]}
    assert all(r["JointI"] in joints and r["JointJ"] in joints for r in t["CONNECTIVITY - FRAME"])
    zs = sorted({float(r["Z"]) for r in t["JOINT COORDINATES"]})
    assert zs == pytest.approx([0, 3.2, 6.4, 9.6, 12.8])


def test_sections_materials_loads_combos(model):
    inp, raw, _text, t = model
    secs = {r["SectionName"]: r for r in t["FRAME SECTION PROPERTIES 01 - GENERAL"]}
    assert set(secs) == {"C40X40", "B30X45"}
    assert float(secs["B30X45"]["t3"]) == 0.45 and float(secs["B30X45"]["t2"]) == 0.3
    assert {r["Material"] for r in t["MATERIAL PROPERTIES 01 - GENERAL"]} == {"C30", "S400"}
    assert [r["LoadPat"] for r in t["LOAD PATTERN DEFINITIONS"]] == ["DEAD", "LIVE", "EX", "EY"]
    assert {r["Case"] for r in t["LOAD CASE DEFINITIONS"]} == {"DEAD", "LIVE", "EX", "EY", "MODAL"}
    seis = {r["LoadPat"]: r for r in t["AUTO SEISMIC - USER COEFFICIENT"]}
    assert float(seis["EX"]["C"]) == pytest.approx(0.165)
    # distributed loads equal the analysis beam loads
    ex = raw["export"]["beam_udl"]
    dead = sum(float(r["FOverLA"]) for r in t["FRAME LOADS - DISTRIBUTED"] if r["LoadPat"] == "DEAD")
    assert dead == pytest.approx(sum(v["D"] for v in ex.values()), rel=1e-5)
    combos: dict[str, dict[str, float]] = {}
    for r in t["COMBINATION DEFINITIONS"]:
        combos.setdefault(r["ComboName"], {})[r["CaseName"]] = float(r["ScaleFactor"])
    assert len(combos) == len(raw["export"]["combo_factors"])


def test_group_sections_and_entry_points(model):
    inp, _raw, _text, _t = model
    from dataclasses import replace
    inp2 = replace(inp, group_sections={"C1": [0.5, 0.5], "B1": [0.35, 0.5]}, parsed=[])
    raw2 = f3.run_frame3d(inp2)
    t = parse_s2k(cte.build_export("s2k", inp2, raw2))
    assert {"C50X50", "B35X50", "C40X40", "B30X45"} == {r["SectionName"] for r in t["FRAME SECTION PROPERTIES 01 - GENERAL"]}
    assert "s2k" in cte.FORMATS and any(d["format"] == "s2k" for d in cte.export_descriptors())


def test_chat_detects_sap2000():
    assert "s2k" in f3.requested_export_formats("خروجی SAP2000 بده")
    assert "s2k" in f3.requested_export_formats("export SAP2000")
    assert f3.is_export_request("export to SAP2000")
