import json

import pytest

from app.application import frame3d_chat_analysis as f3
from app.application import frame3d_followup as fu
from app.application.agent_intent_routing import score_agent_intents
from app.domain.models.agent import EngineeringAgentType

PENDING = "یک قاب سه بعدی بتنی تحلیل کن، پهنه خطر زیاد، خاک II"


def _spec(payload):
    return json.loads(payload["spec"][len(f3.SPEC_TAG):])


def _quick(monkeypatch):
    # keep tests fast: modal/foundation are exercised elsewhere
    real = f3.run_frame3d
    monkeypatch.setattr(f3, "run_frame3d", lambda inp, **kw: real(inp, with_modal=False, with_foundation=False))


@pytest.mark.parametrize("reply", [
    "storeys, bays_x and bays_y farz kon",
    "خودت فرض کن",
    "فرض کن",
    "assume the rest",
    "use defaults",
    "har chi khodet farz kon",
])
def test_assume_reply_detected(reply):
    assert fu.is_assume_reply(reply)


@pytest.mark.parametrize("reply", ["storeys, bays_x and bays_y farz kon", "خودت فرض کن", "assume defaults"])
def test_assume_reply_completes_pending_request(reply, monkeypatch):
    _quick(monkeypatch)
    merged = fu.merge_with_pending(reply, [PENDING])
    assert PENDING in merged
    p = f3.build_frame3d_payload(merged)
    assert p["status"] == "completed", p.get("message")
    assert p["inputs"]["storeys"] == 4 and p["inputs"]["bays_x"] == 3 and p["inputs"]["bays_y"] == 3
    assert len(p["assumed_defaults"]) >= 3
    assert p["seismic_code"] == "IRAN_2800" and p["design_code"] == "MABHAS9"
    md = f3.frame3d_markdown(p)
    assert ("فرض" in md) or ("Assumed" in md)


def test_finglish_assume_reply_answers_in_persian(monkeypatch):
    _quick(monkeypatch)
    p = f3.build_frame3d_payload(fu.merge_with_pending("storeys, bays_x and bays_y farz kon", [PENDING]))
    assert p["lang"] == "fa"


def test_assume_routes_to_analysis():
    top = score_agent_intents("storeys, bays_x and bays_y farz kon")[0]
    assert top.agent_type == EngineeringAgentType.ANALYSIS_AGENT


def test_reply_with_numbers_completes_pending(monkeypatch):
    _quick(monkeypatch)
    p = f3.build_frame3d_payload(fu.merge_with_pending("3 طبقه، 2x2 دهانه", [PENDING]))
    assert p["status"] == "completed"
    assert (p["inputs"]["storeys"], p["inputs"]["bays_x"], p["inputs"]["bays_y"]) == (3, 2, 2)


def test_no_merge_when_previous_frame_complete():
    prev = "3-storey frame, 2x2 bays of 5 m"
    assert fu.merge_with_pending("storeys ro 6 kon", [prev]) == "storeys ro 6 kon"


@pytest.mark.parametrize("text,expected", [
    ("storeys ro 6 kon", {"storeys": 6}),
    ("tabaghe ha ro 5 kon", {"storeys": 5}),
    ("طبقات را ۶ کن", {"storeys": 6}),
    ("make it 6 storeys", {}),  # handled by the main parser ("6 storeys")
    ("دهانه x را ۶ متر کن", {"bay_x_m": 6.0}),
    ("dahane x ro 6 metr kon", {"bay_x_m": 6.0}),
    ("set bay x to 6 m", {"bay_x_m": 6.0}),
    ("bays_x ro 4 kon", {"bays_x": 4}),
    ("تعداد دهانه در جهت y را ۲ کن", {"bays_y": 2}),
    ("sotoon ha ro 50x50 kon", {"column_b_m": 0.5, "column_h_m": 0.5}),
    ("ستون‌ها را ۵۰×۵۰ کن", {"column_b_m": 0.5, "column_h_m": 0.5}),
    ("change beams to 35x50", {"beam_b_m": 0.35, "beam_h_m": 0.5}),
    ("bare mordeh ro 7 kon", {"dead_kn_m2": 7.0}),
    ("بار زنده را ۳ کن", {"live_kn_m2": 3.0}),
    ("ertefa tabaghe ro 3.5 kon", {"storey_height_m": 3.5}),
    ("use Iranian codes", {"seismic_code": "IRAN_2800", "design_code": "MABHAS9"}),
])
def test_model_edits(text, expected):
    e = {k: v for k, v in fu.model_edits(text).items() if not k.startswith("_")}
    for k, v in expected.items():
        assert e.get(k) == v, (text, e)


@pytest.mark.parametrize("text,check", [
    ("storeys ro 6 kon", lambda i: i["storeys"] == 6),
    ("طبقات را ۵ کن", lambda i: i["storeys"] == 5),
    ("دهانه x را ۶ متر کن", lambda i: i["bay_x_m"] == 6.0 and i["bay_y_m"] == 5.0),
    ("change columns to 50x50", lambda i: i["column_b_m"] == 0.5),
    ("bare zende ro 3 kon", lambda i: i["live_kn_m2"] == 3.0),
    ("make it 5 storeys", lambda i: i["storeys"] == 5),
])
def test_edit_modifies_last_model_and_reruns(text, check, monkeypatch):
    _quick(monkeypatch)
    base = f3.build_frame3d_payload("3-storey frame, 2x2 bays of 5 m, zone high, soil II")
    assert base["status"] == "completed"
    assert fu.is_frame_followup(text)
    assert score_agent_intents(text)[0].agent_type == EngineeringAgentType.ANALYSIS_AGENT
    p = f3.build_frame3d_payload(text, _spec(base))
    assert p["status"] == "completed", p.get("message")
    assert p["model_from_project_memory"] is True
    assert check(p["inputs"]), p["inputs"]
    assert p["inputs"]["bays_x"] == 2
    assert p["model_changes"]
    assert p["followup_note"]


def test_us_codes_note(monkeypatch):
    _quick(monkeypatch)
    base = f3.build_frame3d_payload("3-storey frame, 2x2 bays of 5 m")
    p = f3.build_frame3d_payload("storeys ro 4 kon va ACI estefade kon", _spec(base))
    assert p["inputs"]["storeys"] == 4 and "ACI" in p["followup_note"]


def test_3d_frame_without_storeys_is_frame_request_and_assume_completes():
    from app.application import frame3d_chat_analysis as f3
    first = "یک قاب سه بعدی بتنی تحلیل کن، پهنه خطر زیاد، خاک II"
    assert f3.is_frame3d_request(first)
    merged = fu.merge_with_pending("storeys, bays_x and bays_y farz kon", [first])
    p = f3.build_frame3d_payload(merged)
    assert p["status"] == "completed" and p["inputs"]["storeys"] == 4
    import json
    json.dumps(p, allow_nan=False)  # Postgres json rejects Infinity


def test_pending_sections_numbers_do_not_leak_into_storeys():
    from app.application import frame3d_chat_analysis as f3
    merged = fu.merge_with_pending("farz kon", ["قاب سه بعدی تحلیل کن ستون 50x50 تیر 40x50"])
    p = f3.build_frame3d_payload(merged)
    assert p["inputs"]["storeys"] == 4 and p["inputs"]["column_b_m"] == 0.5
