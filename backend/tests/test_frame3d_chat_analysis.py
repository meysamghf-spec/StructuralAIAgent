"""Phase 1: 3D frame analysis from chat (deterministic parser + internal solver)."""

from app.application.agent_intent_routing import resolve_agent_intent
from app.application.engineering_agent_handlers import AnalysisAgentHandler, ConcreteDesignAgentHandler
from app.application.frame3d_chat_analysis import (
    SEISMIC_PROVIDERS,
    build_frame3d_payload,
    frame3d_markdown,
    is_frame3d_request,
    parse_frame3d_request,
)
from app.application.demo_rc_beam_analysis import analyze_simply_supported_rc_beam
from app.domain.models.agent import EngineeringAgentType

PROMPT = (
    "Analyze a 3-storey RC moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, "
    "columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, "
    "live load 2 kN/m2, equivalent static seismic C=0.165 in X and Y."
)


def test_parser_reads_all_prompt_values() -> None:
    inp = parse_frame3d_request(PROMPT)
    assert (inp.storeys, inp.bays_x, inp.bays_y) == (3, 2, 2)
    assert (inp.bay_x_m, inp.bay_y_m, inp.storey_height_m) == (5.0, 5.0, 3.2)
    assert (inp.column_b_m, inp.column_h_m) == (0.40, 0.40)
    assert (inp.beam_b_m, inp.beam_h_m) == (0.30, 0.45)
    assert (inp.fc_mpa, inp.fy_mpa) == (30.0, 400.0)
    assert (inp.dead_kn_m2, inp.live_kn_m2) == (6.0, 2.0)
    assert inp.seismic_c == 0.165  # f'c=30 must not be read as C
    assert inp.seismic_code == "ASSUMED_C"
    assert inp.design_code == "NONE"


def test_regression_against_reference_frame3d_run() -> None:
    """Numbers from /workspace/farasa/frame3d/run_frame3d.py (same model, same solver)."""
    payload = build_frame3d_payload(PROMPT)
    assert payload is not None and payload["status"] == "completed"
    r = payload["results"]
    assert abs(r["max_drift_amplified_pct"] - 2.126) < 0.005
    assert r["max_drift_storey"] == 2
    assert abs(r["beam_max_M_neg_kn_m"] - 179.54) < 0.1
    assert abs(r["beam_max_M_pos_kn_m"] - 89.55) < 0.1
    assert abs(r["beam_max_V_kn"] - 130.27) < 0.1
    assert abs(r["column_max_P_kn"] - 1175.42) < 0.5
    assert abs(r["seismic_weight_kn"] - 3920.17) < 0.1
    bs = payload["base_shear_check"]
    assert abs(bs["V_expected_kn"] - 646.83) < 0.05
    assert bs["status"] == "PASS"
    assert abs(bs["V_reaction_x_kn"] - bs["V_expected_kn"]) < 0.05
    assert r["equilibrium_error_kn"] < 1e-3
    ms = payload["model_summary"]
    assert (ms["nodes"], ms["columns"], ms["beams"]) == (36, 27, 36)
    # per storey and per direction drift rows
    assert {(d["direction"], d["storey"]) for d in payload["drift"]} == {(a, k) for a in "XY" for k in (1, 2, 3)}
    assert len(payload["envelopes"]["beams"]) == 36


def test_results_are_labelled_honestly() -> None:
    payload = build_frame3d_payload(PROMPT)
    assert payload["kind"] == "frame3d_analysis"
    assert "2800" in payload["disclaimer"] and "Mabhas 9" in payload["disclaimer"]
    assert payload["seismic"]["iranian_2800"] is False
    text = frame3d_markdown(payload)
    assert "179.5" in text and "2.13%" in text
    assert "ASSUMED_C" in SEISMIC_PROVIDERS


def test_missing_bays_gives_clear_message() -> None:
    payload = build_frame3d_payload("Analyze a 3-storey RC frame building")
    assert payload["status"] == "MISSING_REQUIRED_INPUT"
    assert "bays" in payload["message"].lower() or "دهانه" in payload["message"]
    assert set(payload["missing_inputs"]) == {"bays_x", "bays_y", "bay_x_m", "bay_y_m"}
    assert "bays_x" not in payload["message"]  # friendly labels, never raw keys


def test_without_seismic_coefficient_runs_gravity_only() -> None:
    payload = build_frame3d_payload("Analyze a 2-storey frame with 2x1 bays of 6 m")
    assert payload["status"] == "completed"
    assert payload["drift"] == [] and payload["base_shear_check"] is None
    assert any("seismic coefficient" in w for w in payload["warnings"])
    assert "slab_t_m" in payload["defaulted_inputs"]


def test_persian_request_is_parsed() -> None:
    payload = build_frame3d_payload("قاب بتنی ۴ طبقه با ۳x۲ دهانه ۶ متر، ضریب زلزله 0.12 را تحلیل کن")
    assert payload["status"] == "completed"
    assert payload["model_summary"]["storeys"] == 4
    assert (payload["model_summary"]["bays_x"], payload["model_summary"]["bays_y"]) == (3, 2)
    assert payload["inputs"]["seismic_c"] == 0.12


def test_size_limit() -> None:
    # ETABS-scale caps (frame3d_limits): 100 storeys, 30 bays, 8000 nodes.
    payload = build_frame3d_payload("Analyze a 50-storey frame with 20x20 bays of 5 m, C=0.1")
    assert payload["status"] == "UNSUPPORTED_SIZE"
    payload = build_frame3d_payload("Analyze a 120-storey frame with 2x2 bays of 5 m, C=0.1")
    assert payload["status"] == "UNSUPPORTED_SIZE"


def test_limits_shared() -> None:
    from app.application import frame3d_limits as fl

    assert fl.within_limits(30, 15, 15)
    assert not fl.within_limits(50, 20, 20)
    assert not fl.within_limits(30, 15, 15, optimisation=True)
    assert fl.limits_payload()["max_nodes"] == fl.MAX_NODES


def test_detection_and_routing() -> None:
    assert is_frame3d_request(PROMPT)
    assert not is_frame3d_request(
        "Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m."
    )
    assert analyze_simply_supported_rc_beam(
        "Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m."
    ) is not None
    assert resolve_agent_intent(PROMPT).agent_type == EngineeringAgentType.ANALYSIS_AGENT


def test_analysis_handler_returns_frame3d_payload() -> None:
    for handler_cls in (AnalysisAgentHandler, ConcreteDesignAgentHandler):
        handler = handler_cls(services=None)  # frame path needs no services
        result = handler.execute(user_request=PROMPT, parameters={}, context={})
        frame = result.structured_output["frame3d_analysis"]
        assert frame["status"] == "completed"
        assert result.structured_output.get("demo_rc_beam") is None
