"""Phase 5: foundation design (hand calcs) and Persian/English result text."""

from __future__ import annotations

import math

import pytest

from app.application import foundation_design as fd
from app.application import frame3d_chat_analysis as f3
from app.application import frame3d_i18n as i18n

BASE = ("3-storey RC intermediate moment frame, 2x2 bays of 5 m, storey height 3.2 m, columns 40x40 cm, beams 30x45 cm, "
        "f'c=30 MPa, fy=400 MPa, Standard 2800, high hazard, soil II, design per Mabhas 9")
FA = ("قاب بتنی متوسط ۳ طبقه با ۲x۲ دهانه ۵ متر، ارتفاع طبقه 3.2 متر، ستون 40x40 و تیر 30x45، خطر نسبی زیاد، نوع خاک ۲، "
      "طبق ۲۸۰۰ تحلیل و طبق مبحث نهم طراحی کن، تنش مجاز خاک ۲۰۰ kPa")


def _single(p_d=600.0, p_l=400.0):
    return {"D": {"N": [0, 0, p_d, 0, 0, 0]}, "L": {"N": [0, 0, p_l, 0, 0, 0]}}, {"1.2D+1.6L": {"D": 1.2, "L": 1.6}}


def test_isolated_footing_hand_calc():
    reac, combos = _single()
    r = fd.design_footing(reac, "N", combos, c1=0.4, c2=0.4, position="interior", qa=200.0, fc=30.0, fy=400.0)
    qnet = 200 - 18 * 1.5                                   # 173 kPa
    assert r["net_pressure_allow_kpa"] == pytest.approx(qnet)
    assert r["B_m"] == pytest.approx(2.5)                   # sqrt(1000/173) = 2.40 -> 2.5 m
    qu = 1.2 * 600 + 1.6 * 400                              # 1360 kN
    assert r["qu_max_kpa"] == pytest.approx(qu / 2.5**2)    # 217.6 kPa (concentric)
    assert r["Mu_kn_m"] == pytest.approx(217.6 * 2.5 * ((2.5 - 0.4) / 2) ** 2 / 2, rel=1e-6)

    def shear_ok(h):
        d = h - 0.075 - 0.010
        vc1 = 0.2 * 0.65 * math.sqrt(30) * 1000 * 2.5 * d
        vu1 = 217.6 * 2.5 * ((2.5 - 0.4) / 2 - d)
        bo = 4 * (0.4 + d)
        vc2 = 0.65 * math.sqrt(30) * 1000 * min(0.2 * 3, 0.2 * (40 * d / bo + 2), 0.4) * bo * d
        vu2 = 217.6 * (2.5**2 - (0.4 + d) ** 2)
        return vu1 <= vc1 and vu2 <= vc2
    assert shear_ok(r["h_m"]) and not shear_ok(round(r["h_m"] - 0.05, 6))   # thickness is the smallest 50 mm step that passes
    assert r["DC_oneway"] <= 1 and r["DC_punching"] <= 1 and r["DC_flexure"] <= 1.0001
    assert r["As_prov_mm2"] >= max(r["As_req_mm2"], 0.0018 * 2500 * r["h_m"] * 1000)


def test_eccentric_footing_obeys_kern():
    reac = {"D": {"N": [0, 0, 600, 0, 0, 0]}, "L": {"N": [0, 0, 400, 300, 0, 0]}}   # Mx = 300 kN·m under D+L
    r = fd.design_footing(reac, "N", {"1.2D+1.6L": {"D": 1.2, "L": 1.6}}, c1=0.4, c2=0.4, position="interior", qa=200.0, fc=30.0, fy=400.0)
    e = 300 / 1000 + 0.0                                      # ey = Mx / P (no shear)
    assert r["B_m"] > 2.5 and e <= r["B_m"] / 6               # larger than the concentric size, resultant inside the kern
    assert r["bearing_dc"] <= 1.0


def test_allowable_bearing_parsing_and_default():
    assert f3.parse_frame3d_request(BASE + ", allowable bearing 250 kPa").allowable_bearing_kpa == 250
    assert f3.parse_frame3d_request(FA).allowable_bearing_kpa == 200
    assert f3.parse_frame3d_request("3 storey frame 2x2 bays, soil bearing capacity 2 kg/cm2").allowable_bearing_kpa == pytest.approx(196.13, abs=0.01)
    p = f3.build_frame3d_payload(BASE)
    assert p["foundation"]["qa_kpa"] == 150 and p["foundation"]["qa_assumed"] is True
    assert any("150 kPa is assumed" in w for w in p["warnings"])
    assert f3.build_frame3d_payload(BASE + ", allowable bearing 200 kPa")["foundation"]["qa_assumed"] is False
    assert f3.build_frame3d_payload(BASE.replace(", design per Mabhas 9", ""))["foundation"] is None
    assert f3.build_frame3d_payload(BASE.replace(", design per Mabhas 9", ", foundation"))["foundation"]["rows"]


def test_frame_foundation_rows_and_group_equilibrium():
    p = f3.build_frame3d_payload(BASE + ", allowable bearing 200 kPa")
    fdn = p["foundation"]
    assert fdn["status"] == "PASS" and {r["position"] for r in fdn["rows"]} == {"corner", "edge", "interior"}
    inp, raw, _ = f3.run_frame3d_for_export({**p["inputs"], "_p": p["parsed_from_request"]})
    total_service = raw["gravity_reaction_kn"]["D"] + raw["gravity_reaction_kn"]["L"]
    sizes = {r["position"]: r for r in fdn["rows"]}
    area = sum(sizes[f["position"]]["B_m"] ** 2 for f in raw["foundation_design"]["footings"])
    assert area * (200 - 27) >= total_service                  # footings together carry the service load
    for r in fdn["rows"]:
        assert r["bearing_dc"] <= 1.0 and r["DC_punching"] <= 1.0 and r["DC_oneway"] <= 1.0


def test_overlap_detected_and_recommendation():
    p = f3.build_frame3d_payload("6-storey RC frame, 2x2 bays of 3 m, storey height 3.2 m, columns 50x50 cm, C=0.165, foundation, allowable bearing 100 kPa")
    ov = p["foundation"]["overlap"]
    assert p["foundation"]["status"] == "OVERLAP" and ov["overlaps"] and ov["min_gap_m"] < 0
    assert "combined" in ov["recommendation"] or "mat" in ov["recommendation"]
    assert any("overlap" in w for w in p["warnings"])


def test_footing_in_dxf_and_f2k():
    from app.application import csi_text_export as cte
    p = f3.build_frame3d_payload(BASE + ", allowable bearing 200 kPa")
    inp, raw, design = f3.run_frame3d_for_export({**p["inputs"], "_p": p["parsed_from_request"]})
    import io

    import ezdxf

    doc = ezdxf.read(io.StringIO(cte.build_export("dxf_plans", inp, raw, design)))
    msp = doc.modelspace()
    assert len(msp.query('LWPOLYLINE[layer=="S-FOOT"]')) == 9
    assert {t.dxf.text for t in msp.query('TEXT[layer=="S-TAG"]')} >= {"F1", "F2", "F3"}
    t = cte.parse_f2k(cte.build_f2k(inp, raw))
    areas = t["OBJECT GEOMETRY - AREAS 01 - GENERAL"]
    assert sum(a["Area"].startswith("FTG") for a in areas) == 9 and areas[0]["Area"].startswith("FTG")
    assert sum(a["Area"].startswith("STF") for a in areas) == 9  # column stiff zones


# ------------------------------------------------------------------ language
def test_language_detection():
    assert i18n.detect_lang(FA) == "fa" and i18n.detect_lang(BASE) == "en"
    assert f3.parse_frame3d_request(FA).lang == "fa"


def test_persian_payload_and_markdown_have_no_english_prose():
    p = f3.build_frame3d_payload(FA)
    assert p["lang"] == "fa" and p["status"] == "completed"
    assert p["message"] == "تحلیل قاب سه‌بعدی انجام شد"
    md = f3.frame3d_markdown(p)
    assert "طراحی فونداسیون" in md and "**وضعیت:** تکمیل شد" in md
    assert "Completed" not in md and "Assumptions" not in md and "Implemented clauses" not in md
    # free-text lists are Persian (identifiers, numbers and symbols stay)
    prose = p["assumptions"] + p["warnings"] + p["foundation"]["clauses_implemented"] + p["design"]["clauses_simplified"] + [p["disclaimer"]]
    for text in prose:
        assert i18n._ARABIC.search(text), text
    english_left = [t for t in prose if any(en in t for en, _ in i18n.PHRASES if len(en) > 25)]
    assert english_left == []
    assert p["design"]["status"] in ("PASS", "CHECK", "FAIL")      # codes stay machine-readable
    assert p["inputs"]["allowable_bearing_kpa"] == 200


def test_english_prompt_stays_english():
    p = f3.build_frame3d_payload(BASE)
    assert p["lang"] == "en" and p["message"] == "3D frame analysis completed"
    md = f3.frame3d_markdown(p)
    assert "**Status:** Completed" in md and "وضعیت" not in md and "تحلیل قاب" not in md


def test_persian_error_and_missing_messages():
    p = f3.build_frame3d_payload("تحلیل قاب سه‌بعدی بتنی چند طبقه با دهانه ۵ متر")
    assert p["status"] == "MISSING_REQUIRED_INPUT" and "تعداد طبقات" in p["message"]
    assert "Please specify" not in p["message"]
    none = f3.build_frame3d_payload("فونداسیون قاب را بده", None)
    assert none["status"] == "MISSING_REQUIRED_INPUT" and none["lang"] == "fa" and i18n._ARABIC.search(none["message"])


def test_foundation_follow_up_from_memory_persian():
    first = f3.build_frame3d_payload(BASE.replace(", design per Mabhas 9", ""))
    spec = f3.prior_frame3d_spec({"memories": [{"content": f3.frame3d_memory_summary(first)[:500]}]})
    follow = f3.build_frame3d_payload("فونداسیون قاب را طراحی کن، تنش مجاز خاک 180 kPa", spec)
    assert follow["model_from_project_memory"] and follow["foundation"]["qa_kpa"] == 180 and follow["foundation"]["qa_assumed"] is False
    assert follow["lang"] == "fa"
    assert f3.is_export_request("فونداسیون قاب را طراحی کن")


# ------------------------------------------------------------------ regression: Meysam's phase-3 prompt
MEYSAM = ("Analyze and design per Mabhas 9 a 3-storey RC intermediate moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, "
          "columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, Standard 2800, "
          "high seismic hazard, soil type II, I=1.")


def test_meysam_prompt_routes_to_frame3d_handler():
    from app.application.agent_intent_routing import score_agent_intents
    from app.application.engineering_agent_handlers import _frame3d_result
    from app.domain.models.agent import EngineeringAgentType

    top = score_agent_intents(MEYSAM)[0]
    assert top.agent_type == EngineeringAgentType.ANALYSIS_AGENT and "3D frame" in top.intent_label
    for agent in (EngineeringAgentType.ANALYSIS_AGENT, EngineeringAgentType.CONCRETE_DESIGN_AGENT):
        res = _frame3d_result(agent_type=agent, action="x", user_request=MEYSAM, parameters={}, context={})
        out = res.structured_output
        assert out["frame3d_analysis"]["status"] == "completed" and out["frame3d_analysis"]["design"]["status"] in ("PASS", "CHECK")
        assert "solver adapter" not in str(out.get("user_summary"))


def test_viewer_payload_consistent_and_compact():
    import json
    p = f3.build_frame3d_payload(MEYSAM)
    v = p["viewer"]
    assert len(json.dumps(v)) < 200_000
    assert set(v["cases"]) >= {"D", "L", "Ex", "Ey"} and v["combos"]["1.2D+1.6L"] == {"D": 1.2, "L": 1.6}
    ids = {n["id"] for n in v["nodes"]}
    assert all(m["i"] in ids and m["j"] in ids for m in v["members"])
    # beam equilibrium: Mj = Mi + L*Vi + w L^2/2
    for m in v["members"]:
        if m["type"] == "beam":
            N, Vi, Mi, Mj, w = v["forces"]["D"][m["id"]]
            assert abs(Mi + 5 * Vi + w * 12.5 - Mj) < 0.1
    assert all(m["dc"] is not None and m["section"] for m in v["members"])
    # base reactions balance the gravity reaction of the D case
    fz = sum(r[2] for r in v["reactions"]["D"].values())
    assert abs(fz - p["gravity_reaction_kn"]["D"]) < 1.0
    assert len(v["footings"]) == 9


def test_manual_run_endpoint_matches_chat_payload():
    from fastapi.testclient import TestClient

    import app.main as main
    from app.api.deps import get_current_account

    chat = f3.build_frame3d_payload(MEYSAM)
    inputs = {k: v for k, v in chat["inputs"].items() if k != "lang"}
    application = getattr(main, "app", None) or main.create_app()
    application.dependency_overrides[get_current_account] = lambda: object()
    try:
        client = TestClient(application)
        r = client.post("/api/v1/frame3d/run", json={"inputs": inputs})
        assert r.status_code == 200, r.text
        p = r.json()["frame3d_analysis"]
        assert p["status"] == "completed" and p["design"]["status"] == chat["design"]["status"]
        assert p["results"]["column_max_P_kn"] == chat["results"]["column_max_P_kn"]
        assert p["viewer"] and p["foundation"] and p["lang"] == "en"
        fa = client.post("/api/v1/frame3d/run", json={"inputs": {**inputs, "lang": "fa"}}).json()["frame3d_analysis"]
        assert fa["lang"] == "fa" and fa["message"] != p["message"]
        bad = client.post("/api/v1/frame3d/run", json={"inputs": {"storeys": 3}}).json()["frame3d_analysis"]
        assert bad["status"] == "MISSING_REQUIRED_INPUT"
    finally:
        application.dependency_overrides.clear()
