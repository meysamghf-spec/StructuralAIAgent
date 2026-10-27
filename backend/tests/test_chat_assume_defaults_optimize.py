"""Replay of the reported SAIA chat bug: «پیش‌فرض‌ها را فرض کن و بهینه کن» must build the default frame and optimize.

Fast unit tests cover the routing functions for many phrasings; a few end-to-end replays cover the multi-turn flow.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application import frame3d_followup as fu
from app.application import frame_optimizer as fopt
from tests.test_chat_workflow_honesty import _chat, _is_optimization_result, _task
from tests.test_api_chat import _project, _register

COMBINED = [
    "پیش‌فرض‌ها را فرض کن و بهینه کن",
    "پیش فرض ها را فرض کن و بهینه کن",
    "پیش‌فرض را فرض کن و بهینه کن",
    "پیشفرض‌ها رو فرض کن بعد بهینه‌سازی کن",
    "پیش‌فرض‌ها را فرض کن، بعد بهینه‌سازی کن",
    "پیش\u200cفرض\u200cها را فرض کن و بهینه\u200cسازی کن",
    "assume defaults and optimize",
    "use defaults then optimize it",
    "Assume the defaults, and optimise",
    "pishfarz ha ro farz kon va behine kon",
    "pish farz ha ro farz kon va behine sazi kon",
    "pishfarz ro farz kon bad behineh kon",
    "پیش‌فرض‌ها را فرض کن و بهینه‌ کن",
]
ALONE = ["پیش‌فرض‌ها را فرض کن", "پیش فرض ها را فرض کن", "پیشفرض را فرض کن", "assume defaults", "use defaults",
         "assume the defaults", "pishfarz ha ro farz kon", "pish farz kon"]
FIRST = ["بهینه‌سازی", "بهینه سازی", "قاب را بهینه کن", "optimize", "optimise the frame", "behine sazi", "behine kon",
         "پیش‌نیازهای بهینه‌سازی چیست؟"]


@pytest.mark.parametrize("text", COMBINED)
def test_combined_message_is_an_optimize_request_with_assume(text: str) -> None:
    assert fopt.is_optimize_request(text), text
    assert fu.is_assume_reply(text), text
    # it is routed to the optimizer on its own (no earlier context needed)
    assert fopt.pending_optimize_text(text, []) == text


@pytest.mark.parametrize("text", ALONE)
@pytest.mark.parametrize("first", FIRST)
def test_assume_alone_after_checklist_merges_with_pending_optimize(text: str, first: str) -> None:
    checklist = fopt.missing_frame_checklist(first)
    assert fopt.is_optimization_checklist(checklist)
    merged = fopt.merge_assume_with_checklist(text, [first], checklist)
    assert fopt.is_optimize_request(merged) and fu.is_assume_reply(merged), (first, text, merged)
    if fopt.is_optimize_request(first):
        # also the plain pending-text path used by the rule-based chat
        assert fopt.is_optimize_request(fopt.pending_optimize_text(text, [first]) or "")


@pytest.mark.parametrize("text", ["assume defaults", "پیش‌فرض‌ها را فرض کن"])
def test_assume_alone_without_checklist_is_not_hijacked(text: str) -> None:
    assert fopt.merge_assume_with_checklist(text, ["hello"], "Here is the beam result.") == text
    assert fopt.pending_optimize_text(text, ["hello"]) is None


@pytest.mark.parametrize("text", ["behine kon", "behine sazi kon", "behineh kon", "بهینه کن", "optimise", "optimize"])
def test_optimize_wording_variants(text: str) -> None:
    assert fopt.is_optimize_request(text)


@pytest.mark.parametrize("text", ["beam be-henar", "how is the weather", "قاب 3 طبقه تحلیل کن", "behinam salam"])
def test_non_optimize_not_matched(text: str) -> None:
    assert not fopt.is_optimize_request(text)


def test_combined_message_builds_default_frame_and_optimizes_without_context() -> None:
    res = fopt.build_optimization_from_chat("پیش‌فرض‌ها را فرض کن و بهینه کن", None, {"time_budget_s": 3})
    assert res is not None
    assumed = res["assumed_defaults"]
    assert {"storeys", "bays_x", "bays_y", "storey_height_m", "column_b_m", "beam_b_m", "design_code"} <= set(assumed)
    assert res["inputs_used"]["storeys"] == fu.DEFAULTS["storeys"]


def _assert_optimized(reply: dict) -> None:
    content = reply["assistant_message"]["content"]
    assert _is_optimization_result(content), content[:400]
    assert "پیش‌نیازها" not in content and "Optimization prerequisites" not in content
    assert "US_CUSTOMARY" not in content and "Partially Completed" not in content


def test_replay_persian_multi_turn_checklist_then_combined_then_alone(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    one = _chat(api_client, token, project_id, "بهینه‌سازی")
    assert "پیش‌نیازها" in one["assistant_message"]["content"]
    two = _chat(api_client, token, project_id, "پیش‌فرض‌ها را فرض کن و بهینه کن", one["conversation_id"])
    _assert_optimized(two)
    assert _task(two)["status"] == "COMPLETED"
    # same conversation, defaults reply alone again after a fresh checklist (new project -> checklist again)
    project2 = _project(api_client, token)
    a = _chat(api_client, token, project2, "قاب را بهینه کن")
    assert "پیش‌نیازها" in a["assistant_message"]["content"]
    _assert_optimized(_chat(api_client, token, project2, "پیش‌فرض‌ها را فرض کن", a["conversation_id"]))


def test_replay_finglish_combined_first_message(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    reply = _chat(api_client, token, project_id, "pishfarz ha ro farz kon va behine kon")
    _assert_optimized(reply)


def test_replay_english_multi_turn(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    one = _chat(api_client, token, project_id, "optimize")
    assert "prerequisites" in one["assistant_message"]["content"].lower()
    _assert_optimized(_chat(api_client, token, project_id, "assume defaults and optimize", one["conversation_id"]))


def test_effective_units_idempotent_and_si_for_legacy_iranian_project() -> None:
    from app.domain.models.pem import (
        UnitSystem, create_iran_default_code_configuration, create_us_customary_unit_configuration,
        effective_unit_configuration)

    legacy = create_us_customary_unit_configuration()
    code = create_iran_default_code_configuration()
    once = effective_unit_configuration(legacy, code)
    twice = effective_unit_configuration(once, code)
    assert once.system == twice.system == UnitSystem.SI_METRIC
    assert (once.force_unit, once.length_unit) == ("kN", "m")
    assert legacy.system == UnitSystem.US_CUSTOMARY  # stored row is never rewritten


@pytest.mark.parametrize("text", COMBINED + ["optimise it", "behine sazi kon", "بهينه کن"])
def test_combined_and_optimize_wording_routes_to_the_optimization_agent(text: str) -> None:
    from app.application.agent_intent_routing import resolve_agent_intent
    from app.domain.models.agent import EngineeringAgentType

    assert resolve_agent_intent(text).agent_type == EngineeringAgentType.OPTIMIZATION_AGENT, text
