"""Phase 3: Mabhas 9 RC design — hand-calculation checks and frame integration."""

import math

import pytest

from app.application import mabhas9_rc_design as m9
from app.application.frame3d_chat_analysis import build_frame3d_payload

FRAME = (
    "Analyze and design per Mabhas 9 a 3-storey RC intermediate moment frame, 2x2 bays of 5 m in X and Y, "
    "storey height 3.2 m, columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, "
    "live load 2 kN/m2, Standard 2800, high seismic hazard, soil type II, I=1."
)


def test_stress_block_factors() -> None:
    assert m9.alpha1(30) == pytest.approx(0.805)
    assert m9.beta1(30) == pytest.approx(0.895)
    assert m9.alpha1(150) == 0.67 and m9.beta1(150) == 0.67


def test_beam_flexure_hand_calc() -> None:
    # b=300, d=390, f'c=30, fy=400, Mu=150 kN·m
    # k = α1·φc·f'c·b = 0.805·0.65·30·300 = 4709.25 N/mm
    # As = k·(d − √(d² − 2Mu/k))/(φs·fy) = 4709.25·(390 − √(152100 − 63704.2))/340 = 1283.8 mm²
    As = m9.beam_required_as(150, 300, 390, 30, 400)
    assert As == pytest.approx(1283.8, abs=0.5)
    a = 0.85 * As * 400 / (0.805 * 0.65 * 30 * 300)
    assert a == pytest.approx(92.69, abs=0.05)
    assert m9.beam_moment_resistance(As, 300, 390, 30, 400) == pytest.approx(150.0, rel=1e-6)
    assert m9.beam_min_steel(300, 390, 30, 400) == pytest.approx(1.4 / 400 * 300 * 390)  # 1.4 governs 0.25√30 = 1.37
    assert m9.beam_required_as(1000, 300, 390, 30, 400) is None  # compression block insufficient


def test_beam_shear_hand_calc() -> None:
    # Vc = 0.2·0.65·√30·300·390 = 83.31 kN; Vu = 200 → Vs = 116.7 kN
    # s = φs·Av·fy·d/Vs = 0.85·157.08·400·390/116.7e3 = 178.5 mm → d/2 = 195 not governing
    sh = m9.beam_shear_design(200, 300, 390, 450, 30, 400, 20, "intermediate")
    assert sh["Vc_kn"] == pytest.approx(83.31, abs=0.01)
    assert sh["s_mid_mm"] == 175
    assert sh["s_end_mm"] == 95  # min(d/4 = 97.5, 8·20, 240, 300) → 95
    vr = sh["Vc_kn"] + 0.85 * 2 * math.pi * 25 * 400 * 390 / 95 / 1000
    assert sh["DC"] == pytest.approx(200 / vr)


def test_column_axial_and_balanced_point_hand_calc() -> None:
    # 400×400, 8Φ20 (3 per face), cover to bar centre 60 mm
    # Pr0 = 0.805·0.65·30·(160000 − 2513.3) + 0.85·400·2513.3 = 3326.7 kN → Pr,max = 0.8·Pr0 = 2661.3 kN
    pts, pmax, ast = m9.interaction_curve(400, 400, 3, 20, 30, 400)
    assert ast == pytest.approx(8 * math.pi * 100)
    assert pmax == pytest.approx(2661.3, abs=0.5)
    # balanced: c = 0.0035/(0.0035+0.002)·340 = 216.4 mm, a = 193.7 mm
    # Cc = 1216.2 kN; top layer +305.7 kN; middle +28.4 kN; bottom −320.4 kN → Pb = 1229.8 kN
    # Mb = 1216.2·0.10315 + 305.7·0.14 + 320.4·0.14 = 213.1 kN·m
    assert m9.column_moment_resistance(1229.8, 400, 400, 3, 20, 30, 400) == pytest.approx(213.1, rel=0.01)
    assert m9.column_moment_resistance(3000, 400, 400, 3, 20, 30, 400) == 0.0


def test_column_group_design_respects_steel_limits() -> None:
    recs = {"c1": [{"combo": "x", "seismic": True, "P": 800.0, "ends": [(120.0, 40.0)]}]}
    d = m9.design_column_group(recs, 400, 400, 30, 400, 2750)
    assert d["status"] == "PASS"
    assert 0.01 <= d["rho"] <= 0.06 and d["DC"] <= 1.0
    big = {"c1": [{"combo": "x", "seismic": True, "P": 5000.0, "ends": [(400.0, 0.0)]}]}
    assert m9.design_column_group(big, 400, 400, 30, 400, 2750)["status"] == "FAIL"


def test_frame_design_under_2800() -> None:
    p = build_frame3d_payload(FRAME)
    d = p["design"]
    assert p["design_code"] == "MABHAS9" and d["code"] == "MABHAS9" and d["ductility"] == "intermediate"
    assert d["member_status"] == "PASS"
    assert len(d["beams"]) == 12 and len(d["columns"]) == 9
    assert all(b["DC_flexure"] <= 1.0 and b["DC_shear"] <= 1.0 for b in d["beams"])
    assert all(1.0 <= c["rho_pct"] <= 6.0 and c["DC"] <= 1.0 for c in d["columns"])
    assert [j["level"] for j in d["scwb"]] == [1, 2]
    assert d["clauses_implemented"] and d["clauses_simplified"]
    assert "Mabhas 9" in p["code"]


def test_design_not_requested_by_default() -> None:
    p = build_frame3d_payload("Analyze a 3-storey frame, 2x2 bays of 5 m, C=0.165")
    assert p["design"] is None and p["design_code"] == "NONE"
