"""P-Δ (second-order) analysis and response-spectrum completion: validation + behaviour tests."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.application import frame3d_chat_analysis as f
from app.application import frame3d_followup as fu
from app.application import frame3d_i18n as i18n
from app.application.analysis.frame3d_solver import (
    SpaceElement, SpaceFrameModel, SpaceNode, SpaceNodalLoad, SpaceSupport,
    assemble_space_system, prepare_second_order, recover_space_result,
)
from app.application.analysis.modal import generalized_eigen_diag_mass, jacobi_eigen

E, B = 30e6, 0.4
A, I = B * B, B**4 / 12 * 0.7


def _cantilever(n: int, length: float):
    nodes = [SpaceNode(f"N{i}", 0, 0, length * i / n) for i in range(n + 1)]
    els = [SpaceElement(f"C{i}", f"N{i}", f"N{i+1}", E, A, I, I, 0.01) for i in range(n)]
    return nodes, els


@pytest.mark.parametrize("ratio", [0.2, 0.5, 0.8])
@pytest.mark.parametrize("axis", [0, 1])
def test_cantilever_matches_exact_beam_column(ratio: float, axis: int) -> None:
    """Tip deflection of an axially loaded cantilever vs the exact tan() solution, and 1/(1-P/Pcr) amplification."""
    length, n, h = 9.6, 8, 10.0
    pcr = math.pi**2 * E * I / (4 * length**2)
    p = ratio * pcr
    nodes, els = _cantilever(n, length)
    load = SpaceNodalLoad(f"N{n}", fx=h) if axis == 0 else SpaceNodalLoad(f"N{n}", fy=h)
    model = SpaceFrameModel("c", nodes, els, [SpaceSupport("N0")], [load], [])
    prep = assemble_space_system(model)
    sec = prepare_second_order(model, prep, {e.id: p for e in els})
    lv = [0.0] * prep["n_full"]
    lv[n * 6 + axis] = h
    u1 = recover_space_result(model, prep, lv).displacements[f"N{n}"][axis]
    u2 = recover_space_result(model, sec, lv).displacements[f"N{n}"][axis]
    k = math.sqrt(p / (E * I))
    exact = h / (p * k) * (math.tan(k * length) - k * length)
    assert u2 == pytest.approx(exact, rel=2e-3)
    assert sec["second_order"]["lambda_cr"] * p == pytest.approx(pcr, rel=2e-3)
    # the classic amplifier is an approximation of the exact tan() solution (good for small P/Pcr)
    if ratio <= 0.5:
        assert u2 / u1 == pytest.approx(1 / (1 - ratio), rel=0.05)


def test_overloaded_column_is_reported_unstable() -> None:
    length, n = 9.6, 4
    pcr = math.pi**2 * E * I / (4 * length**2)
    nodes, els = _cantilever(n, length)
    model = SpaceFrameModel("c", nodes, els, [SpaceSupport("N0")], [SpaceNodalLoad(f"N{n}", fx=1.0)], [])
    prep = assemble_space_system(model)
    with pytest.raises(Exception):
        prepare_second_order(model, prep, {e.id: 1.3 * pcr for e in els})


def test_multi_storey_frame_matches_independent_fictitious_shear_iteration() -> None:
    """3-storey planar-ish frame: K+K_G solve vs a classical iteration with fictitious storey shears P·Δ/h
    (uses only first-order solves, so it is independent of the geometric stiffness)."""
    h, span, ns = 3.2, 5.0, 3
    nodes = [SpaceNode(f"A{k}", 0, 0, h * k) for k in range(ns + 1)] + [SpaceNode(f"B{k}", span, 0, h * k) for k in range(ns + 1)]
    els = []
    for k in range(ns):
        els += [SpaceElement(f"CA{k}", f"A{k}", f"A{k+1}", E, A, I, I, 0.01), SpaceElement(f"CB{k}", f"B{k}", f"B{k+1}", E, A, I, I, 0.01)]
    for k in range(1, ns + 1):
        els.append(SpaceElement(f"G{k}", f"A{k}", f"B{k}", E, 0.3 * 0.5, 0.3 * 0.5**3 / 12 * 0.35, 0.3 * 0.5**3 / 12 * 0.35, 0.01))
    p_col = 0.18 * 0.85 * 25e3 * A  # a heavy compression, ~18% of the squash-like load scale (kN)
    sup = [SpaceSupport("A0"), SpaceSupport("B0")]
    loads = [SpaceNodalLoad(f"A{k}", fx=20.0) for k in range(1, ns + 1)]
    model = SpaceFrameModel("f", nodes, els, sup, loads, [])
    prep = assemble_space_system(model)
    comp = {e.id: (p_col * (ns - int(e.id[2]) ) / ns if e.id.startswith("C") else 0.0) for e in els}
    sec = prepare_second_order(model, prep, comp)
    idx = {nd.id: i for i, nd in enumerate(nodes)}
    lv = [0.0] * prep["n_full"]
    for ld in loads:
        lv[idx[ld.node_id] * 6] = 20.0
    u_kg = recover_space_result(model, sec, lv).displacements
    top_kg = u_kg[f"A{ns}"][0]
    # independent iteration
    u = recover_space_result(model, prep, lv).displacements
    top1 = u[f"A{ns}"][0]
    for _ in range(60):
        add = [0.0] * prep["n_full"]
        for e in els:
            if not e.id.startswith("C"):
                continue
            a, b = e.start_node_id, e.end_node_id
            shear = comp[e.id] * (u[b][0] - u[a][0]) / h
            add[idx[b] * 6] += shear
            add[idx[a] * 6] -= shear
        tot = [x + y for x, y in zip(lv, add, strict=True)]
        u = recover_space_result(model, prep, tot).displacements
    top_it = u[f"A{ns}"][0]
    assert top_kg > top1 * 1.02  # a real second-order effect
    assert top_kg == pytest.approx(top_it, rel=0.04)


def test_eigh_matches_jacobi() -> None:
    rng = np.random.default_rng(3)
    m = rng.normal(size=(9, 9)); k = m @ m.T + 9 * np.eye(9)
    mass = list(rng.uniform(1, 5, 9))
    pairs = generalized_eigen_diag_mass(k.tolist(), mass)
    s_ = np.diag(1 / np.sqrt(mass)); a = s_ @ k @ s_
    wj = sorted(jacobi_eigen(a.tolist())[0])
    assert [p[0] for p in pairs] == pytest.approx(wj, rel=1e-8)
    for lam, phi in pairs:  # K φ = λ M φ and φᵀMφ = 1
        phi = np.asarray(phi)
        assert np.allclose(k @ phi, lam * np.asarray(mass) * phi, atol=1e-8 * max(1.0, lam))
        assert float(phi @ (np.asarray(mass) * phi)) == pytest.approx(1.0, rel=1e-9)


def _run(**kw):
    base = dict(storeys=5, bays_x=3, bays_y=2, seismic_code="IRAN_2800", design_code="MABHAS9")
    base.update(kw)
    return f.run_frame3d(f.Frame3dInputs(**base), with_foundation=False)


def test_one_storey_amplification_is_consistent_with_theta() -> None:
    r = _run(storeys=1, bays_x=2, bays_y=2, column_b_m=0.2, column_h_m=0.2, p_delta="on")
    pd = r["p_delta"]
    th, amp = pd["theta"]["X"][0], pd["amplification"]["X"][0]
    assert 0.02 < th < 0.2
    assert 1 / (1 - th) * 0.99 <= amp <= 1 / (1 - 1.2 * th) * 1.01  # 1/(1-θ) (2800) .. consistent-K_G bound


def test_auto_rule_and_modal_unchanged() -> None:
    thin = dict(storeys=6, bays_x=3, bays_y=3)
    on, off, auto = _run(p_delta="on", **thin), _run(p_delta="off", **thin), _run(p_delta="auto", **thin)
    assert off["p_delta"]["applied"] is False and off["p_delta"]["status"] == "OFF"
    assert on["p_delta"]["applied"] is True
    theta = on["p_delta"]["theta_governing"]
    assert auto["p_delta"]["applied"] == (theta > 0.1)
    # modal results use first-order K: identical regardless of the P-Δ switch
    assert on["modal"]["T_fundamental_s"] == pytest.approx(off["modal"]["T_fundamental_s"], rel=1e-12)
    for d in ("X", "Y"):
        assert on["modal"]["response_spectrum"][d]["V_dynamic_kn"] == pytest.approx(off["modal"]["response_spectrum"][d]["V_dynamic_kn"], rel=1e-12)
    # second-order drift is larger
    assert all(a >= b for a, b in zip(on["p_delta"]["drift_second_order_mm"]["X"], on["p_delta"]["drift_first_order_mm"]["X"], strict=True))


def test_auto_does_not_apply_for_non_2800_but_reports_theta() -> None:
    r = _run(seismic_code="ASSUMED_C", seismic_c=0.15, behaviour_r=5.0, p_delta="auto")
    assert r["p_delta"]["applied"] is False
    assert "theta_max" in r["p_delta"]


def test_rs_torsion_and_member_merge() -> None:
    r = _run(p_delta="off")
    rs = r["rs_design"]
    assert rs and rs["beams_governed_by_rs"] + rs["columns_governed_by_rs"] >= 0
    assert r["modal"]["method"].endswith("5% accidental torsion")
    for d in ("X", "Y"):
        v = r["modal"]["response_spectrum"][d]
        assert v["V_dynamic_scaled_kn"] >= 0.85 * v["V_static_kn"] - 1e-6  # 85% minimum (regular)
    irr = _run(p_delta="off", irregular=True)
    for d in ("X", "Y"):
        v = irr["modal"]["response_spectrum"][d]
        assert v["V_dynamic_scaled_kn"] >= 0.90 * v["V_static_kn"] - 1e-6


def test_parse_p_delta_switches() -> None:
    assert fu.p_delta_request("5 storey frame without P-delta") == "off"
    assert fu.p_delta_request("5 storey frame, with P-delta") == "on"
    assert fu.p_delta_request("بدون p-delta تحلیل کن") == "off"
    assert fu.p_delta_request("5 storey frame") is None
    assert f.parse_frame3d_request("5 storey frame 3x3 bays with P-delta").p_delta == "on"
    assert f.parse_frame3d_request("5 storey frame 3x3 bays no p-delta").p_delta == "off"


def test_no_stale_no_pdelta_text_when_included() -> None:
    r = _run(p_delta="on")
    body = repr(r["p_delta"])
    assert "No P-Δ" not in body
    for en, fa_text in i18n.PHRASES:
        if "P-Δ" in en:
            assert fa_text.strip()


def test_stability_note_depends_on_payload() -> None:
    from app.application.assistant_chat import _stability_note
    on = _run(p_delta="on")["p_delta"]
    off = _run(p_delta="off")["p_delta"]
    pay_on, pay_off = f._p_delta_payload(on), f._p_delta_payload(off)
    assert "second-order (P-Δ) analysis is included" in _stability_note(pay_on, False)
    assert "P-Δ is not included" in _stability_note(pay_off, False)
    assert "انجام شده" in _stability_note(pay_on, True) and "لحاظ نشده" in _stability_note(pay_off, True)
    assert "was computed" in _stability_note(None, False)
