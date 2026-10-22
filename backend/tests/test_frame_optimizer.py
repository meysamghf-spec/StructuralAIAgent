"""Frame optimizer: FSD re-analysis loop + GA (determinism, feasibility, constructability, routing)."""

from __future__ import annotations

import pytest

from app.application import frame3d_chat_analysis as f3
from app.application import frame_optimizer as fopt

OPTS = {"time_budget_s": 60, "max_evaluations": 60, "seed": 7, "ga": {"population": 8, "generations": 4}}


def _inp():
    return f3.inputs_from_dict({"storeys": 2, "bays_x": 1, "bays_y": 1, "bay_x_m": 5, "bay_y_m": 5, "seismic_code": "IRAN_2800"})


@pytest.fixture(scope="module")
def result():
    return fopt.optimize_frame(_inp(), dict(OPTS))


def test_feasible_and_saves(result):
    assert result["kind"] == "frame_optimization"
    assert result["status"] == "completed"
    assert result["optimal"]["feasible"] is True
    assert result["savings_pct"] >= 0
    assert result["optimal"]["objective"] <= result["fsd"]["objective"] + 1
    assert result["optimal"]["max_drift_ratio"] <= result["drift_limit"] + 1e-9
    assert result["convergence"]["fsd"] and result["convergence"]["ga"]
    for g in result["groups"]:
        assert g["governing_constraint"]


def test_constructability(result):
    cols = {g["group"]: int(g["section_cm"].split("x")[0]) for g in result["groups"] if g["type"] == "column"}
    beams = {g["group"]: int(g["section_cm"].split("x")[0]) for g in result["groups"] if g["type"] == "beam"}
    assert cols["C-S2"] <= cols["C-S1"]
    for k, bw in beams.items():
        assert bw <= cols["C-" + k.split("-")[1]]


def test_deterministic(result):
    again = fopt.optimize_frame(_inp(), dict(OPTS))
    assert again["group_sections"] == result["group_sections"]
    assert again["optimal"]["objective"] == result["optimal"]["objective"]


def test_weight_objective_and_report():
    res = fopt.optimize_frame(_inp(), {**OPTS, "objective": "weight", "max_evaluations": 30})
    assert res["method"]["objective"] == "weight"
    assert "|" in fopt.optimization_markdown(res, "en")
    assert fopt.optimization_markdown(res, "fa")


@pytest.mark.parametrize("text", ["optimize this frame", "قاب را بهینه کن", "find the cheapest sections"])
def test_intent(text):
    assert fopt.is_optimize_request(text)


def test_chat_needs_frame():
    assert fopt.build_optimization_from_chat("optimize this frame", None, {}) is None
    assert fopt.missing_frame_message("قاب را بهینه کن")


def test_chat_with_frame_text_fa():
    res = fopt.build_optimization_from_chat(
        "قاب ۲ طبقه ۱x۱ دهانه ۵ متر را بهینه کن", None, {"max_evaluations": 25, "ga": {"population": 6, "generations": 2}}
    )
    assert res is not None and res["kind"] == "frame_optimization"
    assert res["frame"]
