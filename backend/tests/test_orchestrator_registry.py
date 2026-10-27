"""Registry: schema validation, whitelist, permissions, idempotency, confirmation, audit. No database, no network."""
from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from app.application.orchestrator import tools
from app.application.orchestrator.config import OrchestratorSettings, load_settings
from app.application.orchestrator.context import TurnContext
from app.application.orchestrator.registry import (ACCESS_READ, ACCESS_WRITE, SchemaError, Tool, ToolError, ToolRegistry, ToolResult, validate)


class FakePort:
    account_id, conversation_id = "acc-1", "conv-1"

    def __init__(self, project: bool = True, model: dict | None = None) -> None:
        self.project = {"id": "p1", "name": "P"} if project else None
        self._model = model
        self.failures: list[BaseException] = []
        self.analyses = 0

    def list_projects(self): return [{"id": "p1", "name": "P"}, {"id": "p2", "name": "Tower"}]
    def open_project(self, pid): return {"id": pid, "name": "Tower"}
    def create_project(self, name): return {"id": "p9", "name": name}
    def latest_frame_inputs(self): return self._model
    def plan_exports(self): return None
    def check_frame_size(self, inputs): pass
    def consume_analysis(self): self.analyses += 1
    def require_optimization(self): pass
    def usage_snapshot(self): return {}
    def pending_approvals(self): return []
    def report_failure(self, exc): self.failures.append(exc)


def ctx_for(port: FakePort | None = None, fa: bool = True) -> TurnContext:
    return TurnContext(port=port or FakePort(), settings=OrchestratorSettings(mode="always"), fa=fa)


# ------------------------------------------------------------------------------------------------ schema validation
SCHEMA = {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 10}, "x": {"type": "number", "minimum": 0},
                                           "mode": {"type": "string", "enum": ["a", "b"]}, "flag": {"type": "boolean"},
                                           "items": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": ["u", "v", "w"]}}},
          "required": ["n"]}


def test_validate_accepts_and_coerces_numeric_strings_and_persian_digits() -> None:
    assert validate(SCHEMA, {"n": "۵", "x": "2.5", "flag": True}) == {"n": 5, "x": 2.5, "flag": True}
    assert validate(SCHEMA, {"n": 3, "mode": None}) == {"n": 3}


@pytest.mark.parametrize("bad", [{}, {"n": 0}, {"n": 11}, {"n": 1.5}, {"n": "abc"}, {"n": 1, "mode": "c"}, {"n": 1, "extra": 1},
                                 {"n": 1, "items": ["u", "v", "w"]}, {"n": 1, "items": ["z"]}, {"n": True}, {"n": 1, "flag": "yes"}, {"n": 1, "x": -1}])
def test_validate_rejects_bad_arguments(bad: dict[str, Any]) -> None:
    with pytest.raises(SchemaError):
        validate(SCHEMA, bad)


def test_provider_specs_have_no_additional_properties() -> None:
    for spec in tools.get_registry().specs():
        assert "additionalProperties" not in json.dumps(spec)
        assert spec["type"] == "function" and spec["function"]["description"]


# ------------------------------------------------------------------------------------------------ whitelist
FORBIDDEN = ("delete", "drop", "shell", "exec", "sql", "bash", "payment", "pay", "billing", "subscribe", "card", "code", "edit_file", "write_file",
             "approve", "reject", "secret", "token", "deploy", "merge")


def test_registry_is_a_small_explicit_whitelist() -> None:
    names = tools.get_registry().names()
    assert len(names) == len(set(names)) and 8 <= len(names) <= 20
    for n in names:
        assert not any(f in n for f in FORBIDDEN), n
    assert {"analyze_frame", "optimize_frame", "export_files", "get_platform_state"} <= set(names)


def test_unknown_tool_is_rejected_without_side_effects() -> None:
    ctx = ctx_for()
    for name in ("delete_project", "run_shell", "approve_request", "set_plan", "edit_source_code", ""):
        res = tools.get_registry().execute(ctx, name, "{}")
        assert res.status == "unknown_tool" and not res.ok
    assert ctx.port.analyses == 0


def test_invalid_json_and_invalid_args_are_structured_errors() -> None:
    reg, ctx = tools.get_registry(), ctx_for()
    assert reg.execute(ctx, "analyze_frame", "{not json").status == "invalid_arguments"
    assert reg.execute(ctx, "analyze_frame", {"storeys": 99}).status == "invalid_arguments"
    assert reg.execute(ctx, "analyze_frame", {"storeys": 3, "delete_everything": True}).status == "invalid_arguments"
    assert reg.execute(ctx, "export_files", {"files": ["../../etc/passwd"]}).status == "invalid_arguments"
    assert ctx.port.analyses == 0


# ------------------------------------------------------------------------------------------------ permissions / plan limits
def test_plan_limit_is_reported_as_quota_exceeded_not_bypassed() -> None:
    from app.application.billing import service as billing

    port = FakePort()

    def boom() -> None:
        raise billing.QuotaExceededError("optimization", plan={"id": "free", "name": "Free"}, limit=False, upgrade_to="pro")

    port.require_optimization = boom  # type: ignore[method-assign]
    res = tools.get_registry().execute(ctx_for(port), "optimize_frame", {"assume_defaults": True})
    assert res.status == "quota_exceeded" and res.data["code"] == "QUOTA_EXCEEDED"


def test_open_project_only_sees_the_accounts_own_projects() -> None:
    port = FakePort()
    res = tools.get_registry().execute(ctx_for(port), "open_project", {"name": "someone elses secret project"})
    assert res.status == "error" and res.data["code"] == "PROJECT_NOT_FOUND"
    assert set(res.data["your_projects"]) == {"P", "Tower"}
    ok = tools.get_registry().execute(ctx_for(port), "open_project", {"name": "tow"})
    assert ok.ok


def test_tool_needing_a_project_is_blocked_without_one() -> None:
    reg = ToolRegistry()
    reg.register(Tool("t", "d", {"type": "object", "properties": {}}, lambda c, a: ToolResult("ok"), ACCESS_WRITE, needs_project=True))
    assert reg.execute(ctx_for(FakePort(project=False)), "t", {}).status == "error"
    assert reg.execute(ctx_for(FakePort(project=True)), "t", {}).ok


# ------------------------------------------------------------------------------------------------ idempotency
def test_identical_write_calls_in_one_message_run_once() -> None:
    n = {"runs": 0}

    def handler(ctx: Any, args: dict) -> ToolResult:
        n["runs"] += 1
        return ToolResult("ok", {"k": n["runs"]})

    reg = ToolRegistry()
    reg.register(Tool("w", "d", {"type": "object", "properties": {"a": {"type": "integer"}}}, handler, ACCESS_WRITE))
    ctx = ctx_for()
    assert reg.execute(ctx, "w", {"a": 1}).ok
    assert reg.execute(ctx, "w", '{"a": 1}').status == "duplicate"
    assert reg.execute(ctx, "w", {"a": "1"}).status == "duplicate"  # same call after coercion
    assert reg.execute(ctx, "w", {"a": 2}).ok
    assert n["runs"] == 2


def test_analysis_is_consumed_once_per_identical_call() -> None:
    port = FakePort()
    ctx = ctx_for(port)
    args = {"storeys": 2, "bays_x": 1, "bays_y": 1}
    assert tools.get_registry().execute(ctx, "analyze_frame", args).ok
    assert tools.get_registry().execute(ctx, "analyze_frame", args).status == "duplicate"
    assert port.analyses == 1


# ------------------------------------------------------------------------------------------------ confirmation
def test_destructive_overwrite_needs_confirmation_decided_by_the_platform() -> None:
    port = FakePort(model={"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 5, "storey_height_m": 3.2})
    reg, ctx = tools.get_registry(), ctx_for(port)
    res = reg.execute(ctx, "analyze_frame", {"mode": "new", "storeys": 6, "bays_x": 3, "bays_y": 3})
    assert res.status == "confirmation_required" and ctx.pending["tool"] == "analyze_frame" and port.analyses == 0
    # the model cannot confirm by passing a flag
    assert reg.execute(ctx_for(port), "analyze_frame", {"mode": "new", "storeys": 6, "bays_x": 3, "bays_y": 3, "confirmed": True}).status == "invalid_arguments"
    # only the platform (after the user's plain "yes") can add the key
    ctx2 = ctx_for(port)
    ctx2.confirmed.add(ctx.pending["key"])
    done = reg.execute(ctx2, "analyze_frame", ctx.pending["args"])
    assert done.ok and port.analyses == 1 and ctx2.pending is None


def test_editing_the_current_model_needs_no_confirmation() -> None:
    port = FakePort(model={"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 5, "storey_height_m": 3.2})
    ctx = ctx_for(port)
    assert tools.get_registry().execute(ctx, "analyze_frame", {"storeys": 4}).ok and ctx.pending is None


# ------------------------------------------------------------------------------------------------ errors + audit
def test_unexpected_exception_is_reported_and_never_leaked() -> None:
    def handler(ctx: Any, args: dict) -> ToolResult:
        raise RuntimeError("secret internal detail /srv/app/x.py")

    reg = ToolRegistry()
    reg.register(Tool("w", "d", {"type": "object", "properties": {}}, handler, ACCESS_WRITE))
    ctx = ctx_for()
    res = reg.execute(ctx, "w", {})
    assert res.status == "error" and "secret internal detail" not in json.dumps(res.data) + res.text_en + res.text_fa
    assert len(ctx.port.failures) == 1  # goes to the existing auto-report mechanism


def test_expected_tool_error_is_not_reported_as_a_bug() -> None:
    def handler(ctx: Any, args: dict) -> ToolResult:
        raise ToolError("X", "fa", "en")

    reg = ToolRegistry()
    reg.register(Tool("r", "d", {"type": "object", "properties": {}}, handler, ACCESS_READ))
    ctx = ctx_for()
    assert reg.execute(ctx, "r", {}).status == "error" and ctx.port.failures == []


def test_every_call_is_audited_with_redacted_args(caplog) -> None:
    reg = ToolRegistry()
    reg.register(Tool("w", "d", {"type": "object", "properties": {"api_key": {"type": "string"}, "a": {"type": "integer"}}},
                      lambda c, a: ToolResult("ok"), ACCESS_WRITE))
    ctx = ctx_for()
    with caplog.at_level(logging.INFO, logger="saia.orchestrator.audit"):
        reg.execute(ctx, "w", {"api_key": "sk-very-secret", "a": 1})
        reg.execute(ctx, "nope", {})
    assert [t["tool"] for t in ctx.trace] == ["w", "nope"]
    blob = json.dumps(ctx.trace) + caplog.text
    assert "sk-very-secret" not in blob and '"event": "orchestrator_tool"' in caplog.text


# ------------------------------------------------------------------------------------------------ config
def test_config_defaults_are_off_and_safe() -> None:
    s = load_settings({})
    assert s.mode == "off" and not s.enabled and s.provider == "gemini" and s.max_steps == 6 and s.max_tool_calls == 8
    assert load_settings({"PLATFORM_ORCHESTRATOR_MODE": "banana"}).mode == "off"
    assert load_settings({"PLATFORM_ORCHESTRATOR_MODE": "auto"}).enabled
    assert load_settings({"PLATFORM_ORCHESTRATOR_OPTIMIZE_BUDGET_SECONDS": "999"}).optimize_budget_s <= 40
