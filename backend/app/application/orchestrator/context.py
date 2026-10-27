"""Per-message context shared by the tools, and the narrow port the orchestrator uses to reach the platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.application.orchestrator.config import OrchestratorSettings


class PlatformPort(Protocol):
    """Everything the tools may ask of the platform. The real implementation (service_port.py) enforces ownership:
    only projects the account can access are ever listed / opened, and the chat's current project is the only one used."""

    account_id: str
    conversation_id: str
    project: dict[str, str] | None  # {"id", "name"} of the chat's current project

    def list_projects(self) -> list[dict[str, str]]: ...
    def open_project(self, project_id: str) -> dict[str, str]: ...
    def create_project(self, name: str) -> dict[str, str]: ...  # raises billing.QuotaExceededError
    def latest_frame_inputs(self) -> dict[str, Any] | None: ...
    def plan_exports(self) -> Any: ...
    def check_frame_size(self, inputs: dict[str, Any]) -> None: ...  # raises billing.QuotaExceededError
    def consume_analysis(self) -> None: ...  # raises billing.QuotaExceededError
    def require_optimization(self) -> None: ...  # raises billing.QuotaExceededError
    def usage_snapshot(self) -> dict[str, Any]: ...
    def pending_approvals(self) -> list[str]: ...
    def report_failure(self, exc: BaseException) -> None: ...


@dataclass
class TurnContext:
    """State of ONE chat message. Nothing here outlives the message except what is written to its metadata."""

    port: PlatformPort
    settings: OrchestratorSettings
    fa: bool
    cache: dict[str, Any] = field(default_factory=dict)  # idempotency: call key -> ToolResult
    trace: list[dict[str, Any]] = field(default_factory=list)  # audit records of this message
    confirmed: set[str] = field(default_factory=set)  # call keys the USER confirmed in plain words (set by the platform only)
    pending: dict[str, Any] | None = None  # a destructive call waiting for the user's yes/no
    model: dict[str, Any] | None = None  # the working frame inputs (starts from the chat's latest model)
    model_loaded: bool = False
    payload: dict[str, Any] | None = None  # newest engineering_results payload produced in this message
    ui: dict[str, Any] = field(default_factory=dict)  # extra message metadata (project_switch, chat_downloads, ...)
    assumed: list[str] = field(default_factory=list)  # defaults the platform filled in, in this message

    def current_model(self) -> dict[str, Any] | None:
        if not self.model_loaded:
            self.model = self.port.latest_frame_inputs()
            self.model_loaded = True
        return self.model

    def set_model(self, inputs: dict[str, Any]) -> None:
        self.model, self.model_loaded = inputs, True

    def report_failure(self, exc: BaseException) -> None:
        try:
            self.port.report_failure(exc)
        except Exception:  # noqa: BLE001 - reporting must never break the turn
            pass
