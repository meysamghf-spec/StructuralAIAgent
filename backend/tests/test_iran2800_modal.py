"""Phase 2: Standard 2800 (4th ed.) seismic parameters, modal and response-spectrum analysis."""

import math

import pytest

from app.application import iran2800 as s2800
from app.application.analysis.modal import combine_cqc, cqc_coefficient, generalized_eigen_diag_mass
from app.application.frame3d_chat_analysis import build_frame3d_payload, parse_frame3d_request

PHASE1 = (
    "Analyze a 3-storey RC intermediate moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, "
    "columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, "
    "Standard 2800, high seismic hazard, soil type II, I=1."
)


def test_hand_check_c_for_phase1_model_arak() -> None:
    # H = 9.6 m, T = 0.05·9.6^0.75 = 0.2727 s < Ts = 0.5 → B1 = S+1 = 2.5, N = 1; C = 0.30·2.5·1.0/5 = 0.15
    info = s2800.equivalent_static(zone="HIGH", soil="II", importance=1.0, system="RC_IMF", height_m=9.6, storeys=3)
    assert info["T_empirical_s"] == pytest.approx(0.05 * 9.6 ** 0.75)
    assert info["T_empirical_s"] == pytest.approx(0.2727, abs=1e-4)
    assert (info["B1"], info["N"], info["B"]) == (2.5, 1.0, 2.5)
    assert info["C"] == pytest.approx(0.15)
    assert info["C_min"] == pytest.approx(0.12 * 0.30 * 1.0)
    assert info["k"] == 1.0 and info["Cd"] == 4.5 and info["drift_limit"] == 0.025


def test_spectrum_shape_and_n_factor() -> None:
    assert s2800.b1(1.0, "II", "HIGH") == pytest.approx(2.5 * 0.5)  # (S+1)·Ts/T
    assert s2800.n_factor(1.0, "II", "HIGH") == pytest.approx(0.7 * 0.5 / 3.5 + 1)
    assert s2800.n_factor(1.0, "II", "MODERATE") == pytest.approx(0.4 * 0.5 / 3.5 + 1)
    assert s2800.n_factor(5.0, "III", "VERY_HIGH") == 1.7
    assert s2800.b1(0.05, "II", "HIGH") == pytest.approx(1.0 + (1.5 - 1.0 + 1) * 0.5)  # rising branch
    assert s2800.b1(0.05, "II", "HIGH", static=True) == 2.5  # static plateau
    assert s2800.soil_params("IV", "LOW")["S"] == 2.25
    assert s2800.distribution_exponent(1.5) == pytest.approx(1.5)
    assert s2800.distribution_exponent(3.0) == 2.0
    assert s2800.drift_limit(5) == 0.02
    # Cmin governs for a long-period, low-hazard case
    info = s2800.equivalent_static(zone="LOW", soil="I", importance=0.8, system="RC_SMF", height_m=200, storeys=50)
    assert info["C"] == pytest.approx(info["C_min"])


def test_two_dof_shear_building_closed_form() -> None:
    k, m = 1000.0, 2.0
    modes = generalized_eigen_diag_mass([[2 * k, -k], [-k, k]], [m, m])
    expected = sorted([(3 - math.sqrt(5)) / 2 * k / m, (3 + math.sqrt(5)) / 2 * k / m])
    assert [w2 for w2, _ in modes] == pytest.approx(expected)
    phi1 = modes[0][1]
    assert phi1[1] / phi1[0] == pytest.approx((1 + math.sqrt(5)) / 2)  # golden-ratio mode shape
    assert m * phi1[0] ** 2 + m * phi1[1] ** 2 == pytest.approx(1.0)  # mass-normalised


def test_cqc_reduces_to_srss_for_separated_modes_and_sum_for_equal() -> None:
    assert cqc_coefficient(10.0, 10.0) == pytest.approx(1.0)
    assert cqc_coefficient(1.0, 10.0) < 0.01
    assert combine_cqc([3.0, 4.0], [1.0, 100.0]) == pytest.approx(5.0, rel=1e-3)
    assert combine_cqc([3.0, 4.0], [5.0, 5.0]) == pytest.approx(7.0)


def test_single_storey_frame_rs_equals_spectral_force() -> None:
    p = build_frame3d_payload("Analyze a 1-storey RC moment frame with 1x1 bays of 5 m, 2800 high hazard, soil type II")
    modal = p["modal"]
    mx = sum(m["mass_x_pct"] for m in modal["modes"])
    assert mx == pytest.approx(100.0, abs=1e-6)
    t1 = modal["modes"][0]["T_s"]
    W = p["results"]["seismic_weight_kn"]
    sa = 0.30 * s2800.spectral_b(t1, "II", "HIGH") * 1.0 / 5.0
    assert modal["response_spectrum"]["X"]["V_dynamic_kn"] == pytest.approx(sa * W, rel=2e-3)


def test_phase1_model_under_2800_regression() -> None:
    p = build_frame3d_payload(PHASE1)
    assert p["status"] == "completed" and p["seismic_code"] == "IRAN_2800"
    assert p["seismic"]["C"] == pytest.approx(0.15)
    bs = p["base_shear_check"]
    assert bs["V_expected_kn"] == pytest.approx(0.15 * 3920.17, abs=0.05)
    assert bs["status"] == "PASS"
    assert p["results"]["max_drift_amplified_pct"] == pytest.approx(2.485, abs=0.005)  # Cd/I = 4.5
    assert p["drift_check"] == "PASS" and p["drift_reference_limit_pct"] == 2.5
    m = p["modal"]
    assert m["T_fundamental_s"] == pytest.approx(0.829, abs=0.002)
    assert m["modes"][0]["mass_x_pct"] + m["modes"][0]["mass_y_pct"] == pytest.approx(83.25, abs=0.1)
    rs = m["response_spectrum"]["X"]
    assert rs["V_dynamic_kn"] == pytest.approx(325.0, abs=0.5)
    assert rs["scale_factor"] == pytest.approx(0.85 * rs["V_static_kn"] / rs["V_dynamic_kn"], rel=1e-3)
    assert rs["V_dynamic_scaled_kn"] == pytest.approx(0.85 * rs["V_static_kn"], abs=0.05)
    assert "Standard 2800" in p["disclaimer"]


def test_persian_and_english_2800_parsing() -> None:
    fa = parse_frame3d_request("قاب خمشی بتنی ویژه ۴ طبقه با ۳x۳ دهانه ۶ متر، خطر نسبی خیلی زیاد، نوع خاک ۳، ضریب اهمیت ۱.۲")
    assert (fa.seismic_code, fa.zone, fa.soil, fa.importance, fa.system) == ("IRAN_2800", "VERY_HIGH", "III", 1.2, "RC_SMF")
    en = parse_frame3d_request("Analyze a 5 storey steel special moment frame, 3x2 bays of 6 m, moderate seismic hazard, soil type IV, importance factor 1.4")
    assert (en.zone, en.soil, en.importance, en.system) == ("MODERATE", "IV", 1.4, "STEEL_SMF")
    assumed = parse_frame3d_request("Analyze a 3-storey frame, 2x2 bays of 5 m, C=0.165")
    assert assumed.seismic_code == "ASSUMED_C"


def test_defaulted_2800_parameters_are_reported() -> None:
    p = build_frame3d_payload("Analyze a 2-storey frame, 2x2 bays of 5 m, per Standard 2800")
    assert any("assumed" in w and "soil type II" in w for w in p["warnings"])
