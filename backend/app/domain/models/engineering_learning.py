"""Approval-gated engineering experience. Not PEM, and not model-weight training."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LearningScope(StrEnum):
    PROJECT = "PROJECT"
    ENGINEER = "ENGINEER"
    GLOBAL = "GLOBAL"


class LearningApprovalStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


UNAVAILABLE = "UNAVAILABLE"
NOT_CHECKED = "NOT_CHECKED"
LEARNING_AUTHORITY = "CONTEXT_ONLY"


class LearningRecord(BaseModel):
    id: UUID
    project_id: UUID | None = None
    owner_account_id: str
    agent_id: str | None = None
    task_id: UUID | None = None
    source_snapshot_id: UUID | None = None
    source_element_ids: list[str] = Field(default_factory=list)
    source_element_type: str | None = None
    input_context: dict[str, Any] = Field(default_factory=dict)
    agent_output: dict[str, Any] = Field(default_factory=dict)
    human_correction: dict[str, Any] | None = None
    engineering_reason: str | None = None
    validation_result: str = NOT_CHECKED
    approval_status: LearningApprovalStatus = LearningApprovalStatus.CANDIDATE
    learning_scope: LearningScope
    applicability: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LearningRetrieval(BaseModel):
    """Approved experience offered as context. It is not an engineering authority."""

    project_id: UUID
    account_id: str
    records: list[LearningRecord] = Field(default_factory=list)
    explanation: str
    authority: str = LEARNING_AUTHORITY
    overrides_pem: bool = False
    overrides_rules: bool = False
    overrides_qa: bool = False


def learning_explanation(records: list[LearningRecord]) -> str:
    """Explain which approved experience was offered. It is not a code citation."""
    count = len(records)
    if count == 0:
        return (
            "No approved learning records applied. "
            "PEM and explicit rules remain authoritative."
        )
    label = "record" if count == 1 else "records"
    identifiers = ", ".join(str(record.id) for record in records)
    return (
        f"Recommendation used {count} approved learning {label} applicable to this task. "
        "These records are experience context, not code requirements, and do not override the PEM. "
        f"Provenance: {identifiers}."
    )


def experience_statement(record: LearningRecord) -> str:
    """Short experience text. Numeric engineering fields are not copied from agent output."""
    if record.engineering_reason and record.engineering_reason.strip():
        return record.engineering_reason.strip()
    correction = record.human_correction or {}
    reason = correction.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    pattern = record.applicability.get("pattern")
    if isinstance(pattern, str) and pattern.strip():
        return pattern.strip()
    return "Approved engineering experience is available as context only."


def experience_context(record: LearningRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "learning_scope": record.learning_scope.value,
        "agent_id": record.agent_id,
        "source_element_type": record.source_element_type,
        "applicability": record.applicability,
        "confidence": record.confidence,
        "authority": LEARNING_AUTHORITY,
        "statement": experience_statement(record),
    }


def _present(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == UNAVAILABLE:
        return None
    return text


def provenance_view(record: LearningRecord) -> dict[str, Any]:
    """Reviewer-facing chain. Missing links stay UNAVAILABLE instead of being invented."""
    stored = dict(record.provenance)
    return {
        "learning_record_id": str(record.id),
        "task_id": _present(stored.get("task_id"))
        or (_present(record.task_id) or UNAVAILABLE),
        "agent_id": _present(stored.get("agent_id")) or _present(record.agent_id) or UNAVAILABLE,
        "source_snapshot_id": _present(stored.get("source_snapshot_id"))
        or (_present(record.source_snapshot_id) or UNAVAILABLE),
        "source_element_ids": list(record.source_element_ids),
        "source_element_type": record.source_element_type or UNAVAILABLE,
        "engineering_result_id": _present(stored.get("engineering_result_id")) or UNAVAILABLE,
        "qa_result": record.validation_result or UNAVAILABLE,
        "human_decision": record.approval_status.value,
        "learning_scope": record.learning_scope.value,
        "project_id": str(record.project_id) if record.project_id else UNAVAILABLE,
        "owner_account_id": record.owner_account_id,
    }


def authoritative_outcome(
    *,
    pem_value: Any = None,
    rule_value: Any = None,
    qa_status: str | None = None,
    learning_suggestion: Any = None,
) -> dict[str, Any]:
    """Learning never supplies the engineering result.

    PEM, an explicit rule, and QA each outrank a learned suggestion. A
    NOT_CHECKED QA state stays NOT_CHECKED.
    """
    del learning_suggestion  # accepted so callers can show it was ignored
    if qa_status == NOT_CHECKED:
        return {"value": NOT_CHECKED, "authority": "QA", "learning_applied": False}
    if rule_value is not None:
        return {"value": rule_value, "authority": "ENGINEERING_RULE", "learning_applied": False}
    if pem_value is not None:
        return {"value": pem_value, "authority": "PEM", "learning_applied": False}
    return {
        "value": "N/A — not available in PEM",
        "authority": "PEM",
        "learning_applied": False,
    }
