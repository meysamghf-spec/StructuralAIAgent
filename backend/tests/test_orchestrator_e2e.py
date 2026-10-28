"""End-to-end replays through POST /api/v1/chat with a scripted model in place of Gemini (no network)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.orchestrator import engine
from app.application.orchestrator.llm import set_llm_for_tests
from tests.orch_helpers import ScriptedLLM, call, down, say, tool_msg, tool_results
from tests.test_api_chat import _register
from tests.test_chat_workflow_honesty import _chat
from tests.test_api_chat import _project


@pytest.fixture(autouse=True)
def _orch(monkeypatch):
    monkeypatch.setenv("PLATFORM_ORCHESTRATOR_MODE", "always")
    engine.reset_rate_limits()
    yield
    set_llm_for_tests(None)


def _setup(api_client: TestClient):
    token = _register(api_client)
    return token, _project(api_client, token)


def _meta(reply: dict) -> dict:
    return reply["assistant_message"]["metadata"]


def _text(reply: dict) -> str:
    return reply["assistant_message"]["content"]


def _final_from_results(messages, tool_choice):
    res = tool_results(messages)
    last = res[-1]
    return say(f"done: {last.get('status')}")


# ------------------------------------------------------------------------------------------------ scenarios
def test_persian_build_analyze_optimize_in_one_message(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    seen: dict = {}

    def final(messages, tc):
        r = tool_results(messages)
        seen["analysis"], seen["opt"] = r[-2], r[-1]
        return say("قاب ۵ طبقه ۳ دهانه ساخته، تحلیل و بهینه شد؛ جزئیات در کارت نتایج است.")

    llm = ScriptedLLM([
        tool_msg(call("analyze_frame", {"storeys": 5, "bays_x": 3, "bays_y": 3, "assume_defaults": True})),
        tool_msg(call("optimize_frame", {"time_budget_s": 5})),
        final,
    ])
    set_llm_for_tests(llm)
    reply = _chat(api_client, token, pid, "یک قاب ۵ طبقه ۳ دهانه بساز، تحلیل کن و بهینه کن")
    meta = _meta(reply)
    assert meta["mode"] == "orchestrated"
    assert "قاب ۵ طبقه" in _text(reply)
    assert seen["analysis"]["status"] == "ok" and seen["opt"]["status"] == "ok"
    tools = [t["tool"] for t in meta["orchestrator"]["trace"]]
    assert tools == ["analyze_frame", "optimize_frame"]
    assert meta["engineering_results"]["kind"] == "frame_optimization"
    assert meta["orchestrator"]["model"]["storeys"] == 5
    assert meta["orchestrator"]["llm_calls"] == 3
    assert meta["assumed_defaults"]
    # the system prompt is grounded and in persona; history/state reach the model
    first = llm.calls[0]["messages"][0]["content"]
    assert "chief structural engineer" in first and "Generated platform facts" in first


def test_finglish_command(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    llm = ScriptedLLM([tool_msg(call("analyze_frame", {"storeys": 4, "bays_x": 2, "bays_y": 2, "assume_defaults": True})),
                       say("قاب ۴ طبقه تحلیل شد.")])
    set_llm_for_tests(llm)
    reply = _chat(api_client, token, pid, "yek ghab 4 tabaghe 2 dahane besaz va tahlil kon")
    assert _meta(reply)["engineering_results"]["kind"] == "frame3d_analysis"
    assert "persian" in llm.calls[0]["messages"][0]["content"].lower()


def test_english_command_and_exports(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    llm = ScriptedLLM([
        tool_msg(call("analyze_frame", {"storeys": 3, "bays_x": 2, "bays_y": 2})),
        tool_msg(call("export_files", {"files": ["e2k", "report_pdf"]})),
        say("Built a 3-storey frame, analysed it, and prepared the ETABS file and the report."),
    ])
    set_llm_for_tests(llm)
    reply = _chat(api_client, token, pid, "Build a 3 storey 2x2 bay frame, analyse it and give me the e2k and the report")
    meta = _meta(reply)
    assert meta["mode"] == "orchestrated"
    assert meta.get("chat_downloads")
    assert "ETABS" in _text(reply)


def test_missing_inputs_are_assumed_and_stated(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    got: dict = {}

    def second(messages, tc):
        got["r"] = tool_results(messages)[-1]
        return say("فرض کردم ۴ طبقه و ۳×۳ دهانه ۵ متری.")

    set_llm_for_tests(ScriptedLLM([tool_msg(call("analyze_frame", {"assume_defaults": True})), second]))
    reply = _chat(api_client, token, pid, "یک ساختمان بتنی بساز و تحلیل کن")
    assert got["r"]["status"] == "ok"
    assert _meta(reply)["assumed_defaults"]
    assert _meta(reply)["engineering_results"]["status"] == "completed"


def test_without_assume_defaults_the_tool_reports_missing_inputs(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    got: dict = {}

    def second(messages, tc):
        got["r"] = tool_results(messages)[-1]
        return say("تعداد طبقه و دهانه را بفرمایید.")

    set_llm_for_tests(ScriptedLLM([tool_msg(call("analyze_frame", {})), second]))
    reply = _chat(api_client, token, pid, "قاب بساز")
    assert got["r"]["status"] == "missing_inputs"
    assert "engineering_results" not in _meta(reply)


def test_new_model_over_existing_needs_user_confirmation(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    set_llm_for_tests(ScriptedLLM([tool_msg(call("analyze_frame", {"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 5})), say("ok model 1")]))
    first = _chat(api_client, token, pid, "یک قاب ۳ طبقه ۲ دهانه تحلیل کن")
    cid = first["conversation_id"]
    llm = ScriptedLLM([
        tool_msg(call("analyze_frame", {"mode": "new", "storeys": 6, "bays_x": 3, "bays_y": 3, "bay_x_m": 5, "bay_y_m": 5})),
        say("مدل فعلی جایگزین شود؟ (بله/خیر)"),
        say("قاب ۶ طبقه تحلیل شد."),
    ])
    set_llm_for_tests(llm)
    second = _chat(api_client, token, pid, "یک قاب ۶ طبقه ۳ دهانه جدید بساز", cid)
    meta = _meta(second)
    assert meta["orchestrator"]["pending"]["tool"] == "analyze_frame"
    assert "engineering_results" not in meta  # nothing ran
    assert tool_results(llm.calls[1]["messages"])[-1]["status"] == "confirmation_required"
    third = _chat(api_client, token, pid, "بله", cid)
    m3 = _meta(third)
    assert m3["engineering_results"]["inputs"]["storeys"] == 6
    assert "pending" not in m3["orchestrator"]


def test_declining_a_confirmation_changes_nothing(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    set_llm_for_tests(ScriptedLLM([tool_msg(call("analyze_frame", {"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 5})), say("ok")]))
    cid = _chat(api_client, token, pid, "یک قاب ۳ طبقه ۲ دهانه تحلیل کن")["conversation_id"]
    set_llm_for_tests(ScriptedLLM([tool_msg(call("analyze_frame", {"mode": "new", "storeys": 6, "bays_x": 3, "bays_y": 3, "bay_x_m": 5, "bay_y_m": 5})), say("تایید می‌کنید؟")]))
    _chat(api_client, token, pid, "یک قاب جدید بساز", cid)
    llm = ScriptedLLM([])  # no model call may happen on a plain "no"
    set_llm_for_tests(llm)
    reply = _chat(api_client, token, pid, "نه", cid)
    assert llm.calls == [] and "engineering_results" not in _meta(reply)


def test_model_outage_falls_back_to_rule_based_pipeline(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    set_llm_for_tests(ScriptedLLM([down()]))
    reply = _chat(api_client, token, pid, "یک قاب ۳ طبقه ۲ دهانه تحلیل کن")
    meta = _meta(reply)
    assert meta.get("mode") != "orchestrated"
    assert meta["engineering_results"]["kind"] == "frame3d_analysis"  # the rule-based engine still answered


def test_outage_after_tools_ran_returns_the_raw_results(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    set_llm_for_tests(ScriptedLLM([tool_msg(call("analyze_frame", {"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 5})), down()]))
    reply = _chat(api_client, token, pid, "یک قاب ۳ طبقه ۲ دهانه بساز و بهینه کن")
    meta = _meta(reply)
    assert meta["orchestrator"]["degraded"] is True
    assert meta["engineering_results"]["status"] == "completed"
    assert _text(reply).strip()


def test_quota_is_explained_not_bypassed(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("BILLING_ENFORCEMENT", "1")
    token, pid = _setup(api_client)
    got: dict = {}

    def second(messages, tc):
        got["r"] = tool_results(messages)[-1]
        return say("بهینه‌سازی در پلن رایگان فعال نیست.")

    set_llm_for_tests(ScriptedLLM([tool_msg(call("optimize_frame", {"assume_defaults": True})), second]))
    reply = _chat(api_client, token, pid, "قاب را بهینه کن")
    assert got["r"]["status"] == "quota_exceeded"
    assert "engineering_results" not in _meta(reply)


def test_off_mode_never_touches_the_model(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_ORCHESTRATOR_MODE", "off")
    token, pid = _setup(api_client)
    llm = ScriptedLLM([])
    set_llm_for_tests(llm)
    reply = _chat(api_client, token, pid, "یک قاب ۳ طبقه ۲ دهانه تحلیل کن")
    assert llm.calls == [] and _meta(reply)["engineering_results"]["kind"] == "frame3d_analysis"


def test_project_tools_open_and_create(api_client: TestClient) -> None:
    token, pid = _setup(api_client)
    set_llm_for_tests(ScriptedLLM([tool_msg(call("create_project", {"name": "Tower A"})), say("پروژه Tower A ساخته شد.")]))
    reply = _chat(api_client, token, pid, "یک پروژه جدید به نام Tower A بساز")
    assert _meta(reply)["project_switch"]["name"] == "Tower A"
