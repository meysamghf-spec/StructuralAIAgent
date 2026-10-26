"""Optimization chat: honest workflow block, unit defaults by design code, consistent defaults, assume-reply routing."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application import frame3d_chat_analysis as f3
from app.application import frame3d_followup as fu
from app.application import frame_optimizer as fopt
from app.application import optimization_checklist as oc
from app.application.conversation_service import _format_engineering_task_section
from app.domain.models.pem import (
    UnitConfigurationStatus,
    UnitSystem,
    create_iran_default_code_configuration,
    create_si_unit_configuration,
    create_software_default_code_configuration,
    create_us_customary_unit_configuration,
    effective_unit_configuration,
)
from tests.test_api_chat import _headers, _project, _register


# --- (1) units follow the design code -------------------------------------------------------------------------
def test_legacy_us_default_units_on_iranian_project_resolve_to_si() -> None:
    legacy = create_us_customary_unit_configuration()
    assert legacy.status == UnitConfigurationStatus.DEFAULT
    eff = effective_unit_configuration(legacy, create_iran_default_code_configuration())
    assert eff.system == UnitSystem.SI_METRIC
    assert legacy.system == UnitSystem.US_CUSTOMARY  # stored value untouched


def test_user_confirmed_us_units_are_kept_on_iranian_project() -> None:
    units = create_us_customary_unit_configuration().model_copy(update={"status": UnitConfigurationStatus.USER_CONFIRMED})
    assert effective_unit_configuration(units, create_iran_default_code_configuration()) is units


def test_us_code_project_keeps_us_units_and_si_stays_si() -> None:
    us_units = create_us_customary_unit_configuration()
    us_code = create_software_default_code_configuration()
    assert us_code.jurisdiction.value != "IRAN"
    assert effective_unit_configuration(us_units, us_code) is us_units
    si = create_si_unit_configuration()
    assert effective_unit_configuration(si, create_iran_default_code_configuration()) is si


# --- (3) the example command and the assumed defaults describe the same frame -----------------------------------
def test_example_command_matches_documented_defaults() -> None:
    inp = f3.parse_frame3d_request(oc.EXAMPLE_COMMAND_EN)
    assert (inp.storeys, inp.bays_x, inp.bays_y, inp.bay_x_m) == (
        fu.DEFAULTS["storeys"], fu.DEFAULTS["bays_x"], fu.DEFAULTS["bays_y"], fu.DEFAULTS["bay_x_m"])
    inp_fa = f3.parse_frame3d_request(oc.EXAMPLE_COMMAND_FA)
    assert (inp_fa.storeys, inp_fa.bays_x, inp_fa.bays_y, inp_fa.bay_x_m) == (inp.storeys, inp.bays_x, inp.bays_y, inp.bay_x_m)
    assert fopt.is_optimize_request(oc.EXAMPLE_COMMAND_EN) and fopt.is_optimize_request(oc.EXAMPLE_COMMAND_FA)
    assert f"{fu.DEFAULTS['storeys']} storeys" in oc.AUTO_ASSUMPTIONS_EN[0]
    check = oc.checklist_for_chat(has_frame=False)
    assert "3-storey" not in oc.checklist_markdown(check, "en")
    assert oc.EXAMPLE_COMMAND_FA in oc.checklist_markdown(check, "fa")
    assert oc.EXAMPLE_COMMAND_EN in oc.checklist_markdown(check, "en")


# --- (4) merge helper -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("first,reply", [("بهینه‌سازی", "پیش‌فرض‌ها را فرض کن"), ("optimize", "assume defaults")])
def test_assume_reply_after_checklist_merges_with_optimize_request(first, reply) -> None:
    checklist = fopt.missing_frame_checklist(first)
    assert fopt.is_optimization_checklist(checklist)
    merged = fopt.merge_assume_with_checklist(reply, [first], checklist)
    assert merged != reply and fopt.is_optimize_request(merged) and fu.is_assume_reply(merged)


def test_assume_reply_without_checklist_is_not_merged() -> None:
    assert fopt.merge_assume_with_checklist("assume defaults", ["optimize"], "Here is the beam result.") == "assume defaults"
    assert fopt.merge_assume_with_checklist("assume defaults", ["optimize"], None) == "assume defaults"


# --- (2) workflow block rendering -------------------------------------------------------------------------------
_TASK = {
    "status": "WAITING_FOR_INPUT",
    "original_request": "بهینه‌سازی",
    "steps": [
        {"title": "Understand engineer goal", "status": "EXECUTED"},
        {"title": "Validate required inputs", "status": "EXECUTED"},
        {"title": "Execute specialist assistant work", "status": "BLOCKED",
         "missing_inputs": ["Structural model (required inputs)"]},
        {"title": "Validate and record results", "status": "PLANNED"},
    ],
    "assumptions": [
        {"field_name": "Design code", "value": "INBC (Mabahes Melli)", "source": "PROJECT_CONFIGURED"},
        {"field_name": "Unit system", "value": "SI_METRIC", "source": "PROJECT_CONFIGURED"},
    ],
    "missing_required_inputs": ["Structural model (required inputs)"],
}


def test_workflow_section_is_persian_and_does_not_claim_unrun_steps_completed() -> None:
    text = _format_engineering_task_section(_TASK, "fa")
    done, _, rest = text.partition("مسدود")
    assert "اجرای کار دستیار تخصصی" not in done and "اعتبارسنجی و ثبت نتایج" not in done
    assert "اجرای کار دستیار تخصصی — در انتظار: مدل سازه" in rest
    assert "در انتظار اجرا" in rest and "اعتبارسنجی و ثبت نتایج" in rest
    assert "Completed" not in text and "SI (kN، m، MPa)" in text and "US_CUSTOMARY" not in text


def test_workflow_section_english_lists_blocked_and_pending() -> None:
    text = _format_engineering_task_section(_TASK, "en")
    completed = text.split("Completed:")[1].split("Blocked")[0]
    assert "Execute specialist assistant work" not in completed and "Validate and record results" not in completed
    assert "Blocked:" in text and "waiting for: Structural model" in text and "Pending:" in text


# --- end-to-end ---------------------------------------------------------------------------------------------------
def _chat(api_client: TestClient, token: str, project_id: str, message: str, conversation_id: str | None = None) -> dict:
    body = {"message": message, "project_id": project_id}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = api_client.post("/api/v1/chat", json=body, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _task(reply: dict) -> dict:
    return reply["assistant_message"]["metadata"]["engineering_task"]


def _is_optimization_result(content: str) -> bool:
    return "بهینه‌سازی قاب" in content or "Frame optimization" in content


@pytest.mark.parametrize("first", ["بهینه‌سازی", "قاب را بهینه کن"])
def test_persian_optimize_without_frame_is_honest_then_assume_defaults_optimizes(api_client: TestClient, first: str) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)

    one = _chat(api_client, token, project_id, first)
    content = one["assistant_message"]["content"]
    assert "پیش‌نیازها" in content and "❌" in content
    # the user's default frame is described by the same numbers as the assumption text
    assert oc.EXAMPLE_COMMAND_FA in content
    task = _task(one)
    by_title = {s["title"]: s["status"] for s in task["steps"]}
    assert task["status"] == "WAITING_FOR_INPUT"
    assert by_title["Execute specialist assistant work"] == "BLOCKED"
    assert by_title["Validate and record results"] == "PLANNED"
    assert "گردش‌کار مهندسی" in content and "مدل سازه (ورودی‌های لازم)" in content
    assert "Partially Completed" not in content and "US_CUSTOMARY" not in content
    done = content.split("انجام‌شده:")[1].split("مسدود")[0]
    assert "اجرای کار دستیار تخصصی" not in done and "اعتبارسنجی و ثبت نتایج" not in done

    two = _chat(api_client, token, project_id, "پیش‌فرض‌ها را فرض کن", one["conversation_id"])
    assert _is_optimization_result(two["assistant_message"]["content"])
    task2 = _task(two)
    assert task2["status"] == "COMPLETED"
    assert {s["status"] for s in task2["steps"]} == {"EXECUTED"}


def test_english_optimize_without_frame_checklist_stays_english(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    one = _chat(api_client, token, project_id, "optimize")
    content = one["assistant_message"]["content"]
    assert "Engineering workflow" in content and "Blocked:" in content and "Pending:" in content
    assert not any("\u0600" <= ch <= "\u06ff" for ch in content)
    two = _chat(api_client, token, project_id, "assume defaults", one["conversation_id"])
    assert _is_optimization_result(two["assistant_message"]["content"])


def test_new_iranian_project_reports_si_units(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    one = _chat(api_client, token, project_id, "optimize")
    units = [a for a in _task(one).get("assumptions", []) if a.get("field_name") == "Unit system"]
    assert all(a["value"] == "SI_METRIC" for a in units)
