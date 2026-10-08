"""Approval-gated engineering experience. Retrieval is context, never authority."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.application.exceptions import (
    LearningAuthorizationError,
    LearningInvalidStateError,
    LearningRecordNotFoundError,
    LearningSafetyError,
)
from app.domain.models.engineering_learning import (
    LEARNING_AUTHORITY,
    NOT_CHECKED,
    UNAVAILABLE,
    LearningApprovalStatus,
    LearningRecord,
    LearningRetrieval,
    LearningScope,
    learning_explanation,
    provenance_view,
)
from app.infrastructure.repositories.postgres_engineering_learning_repository import (
    PostgresEngineeringLearningRepository,
)

_DECISIONS: dict[LearningApprovalStatus, frozenset[LearningApprovalStatus]] = {
    LearningApprovalStatus.REVIEW: frozenset({LearningApprovalStatus.CANDIDATE}),
    LearningApprovalStatus.APPROVED: frozenset(
        {LearningApprovalStatus.CANDIDATE, LearningApprovalStatus.REVIEW}
    ),
    LearningApprovalStatus.REJECTED: frozenset(
        {LearningApprovalStatus.CANDIDATE, LearningApprovalStatus.REVIEW}
    ),
}


def _link(value: Any) -> str:
    if value is None:
        return UNAVAILABLE
    text = str(value).strip()
    return text or UNAVAILABLE


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


class EngineeringLearningService:
    def __init__(self, repository: PostgresEngineeringLearningRepository) -> None:
        self._records = repository

    def create_candidate(
        self,
        *,
        owner_account_id: str,
        learning_scope: LearningScope,
        project_id: UUID | None = None,
        agent_id: str | None = None,
        task_id: UUID | None = None,
        source_snapshot_id: UUID | None = None,
        source_element_ids: list[str] | None = None,
        source_element_type: str | None = None,
        input_context: dict[str, Any] | None = None,
        agent_output: dict[str, Any] | None = None,
        human_correction: dict[str, Any] | None = None,
        engineering_reason: str | None = None,
        validation_result: str = NOT_CHECKED,
        applicability: dict[str, Any] | None = None,
        confidence: float | None = None,
        engineering_result_id: str | None = None,
    ) -> LearningRecord:
        context = dict(input_context or {})
        self._reject_unchecked_pass(context, validation_result)
        if learning_scope == LearningScope.PROJECT and project_id is None:
            raise LearningSafetyError(
                "PROJECT learning requires a project.",
                details={"learning_scope": learning_scope.value},
            )
        provenance = {
            "task_id": _link(task_id),
            "agent_id": _link(agent_id),
            "source_snapshot_id": _link(source_snapshot_id),
            "engineering_result_id": _link(engineering_result_id),
            "qa_result": validation_result or NOT_CHECKED,
            "human_decision": LearningApprovalStatus.CANDIDATE.value,
        }
        record = LearningRecord(
            id=uuid4(),
            project_id=project_id,
            owner_account_id=owner_account_id,
            agent_id=_clean(agent_id),
            task_id=task_id,
            source_snapshot_id=source_snapshot_id,
            source_element_ids=list(source_element_ids or []),
            source_element_type=_clean(source_element_type),
            input_context=context,
            agent_output=dict(agent_output or {}),
            human_correction=human_correction,
            engineering_reason=engineering_reason,
            validation_result=validation_result or NOT_CHECKED,
            approval_status=LearningApprovalStatus.CANDIDATE,
            learning_scope=learning_scope,
            applicability=dict(applicability or {}),
            confidence=confidence,
            provenance=provenance,
        )
        return self._records.create(record)

    def record_correction(
        self,
        *,
        project_id: UUID,
        owner_account_id: str,
        original_output: dict[str, Any],
        corrected_result: dict[str, Any],
        reason: str | None = None,
        learning_scope: LearningScope = LearningScope.PROJECT,
        agent_id: str | None = None,
        task_id: UUID | None = None,
        source_snapshot_id: UUID | None = None,
        source_element_ids: list[str] | None = None,
        source_element_type: str | None = None,
        applicability: dict[str, Any] | None = None,
        validation_result: str = NOT_CHECKED,
        engineering_result_id: str | None = None,
        input_context: dict[str, Any] | None = None,
    ) -> LearningRecord:
        correction = {
            "corrected_result": corrected_result,
            "reason": reason,
        }
        context = dict(input_context or {})
        context.setdefault("correction_captured", True)
        return self.create_candidate(
            owner_account_id=owner_account_id,
            learning_scope=learning_scope,
            project_id=project_id,
            agent_id=agent_id,
            task_id=task_id,
            source_snapshot_id=source_snapshot_id,
            source_element_ids=source_element_ids,
            source_element_type=source_element_type,
            input_context=context,
            agent_output=original_output,
            human_correction=correction,
            engineering_reason=reason,
            validation_result=validation_result,
            applicability=applicability,
            engineering_result_id=engineering_result_id,
        )

    def mark_review(
        self,
        record_id: UUID,
        *,
        project_id: UUID,
        account_id: str,
    ) -> LearningRecord:
        return self._decide(
            record_id,
            project_id=project_id,
            account_id=account_id,
            target=LearningApprovalStatus.REVIEW,
        )

    def approve(
        self,
        record_id: UUID,
        *,
        project_id: UUID,
        account_id: str,
        note: str | None = None,
    ) -> LearningRecord:
        return self._decide(
            record_id,
            project_id=project_id,
            account_id=account_id,
            target=LearningApprovalStatus.APPROVED,
            reason=note,
        )

    def reject(
        self,
        record_id: UUID,
        *,
        project_id: UUID,
        account_id: str,
        reason: str | None = None,
    ) -> LearningRecord:
        return self._decide(
            record_id,
            project_id=project_id,
            account_id=account_id,
            target=LearningApprovalStatus.REJECTED,
            reason=reason,
        )

    def get(
        self,
        record_id: UUID,
        *,
        project_id: UUID,
        account_id: str,
    ) -> LearningRecord:
        return self._require_visible(record_id, project_id=project_id, account_id=account_id)

    def provenance(
        self,
        record_id: UUID,
        *,
        project_id: UUID,
        account_id: str,
    ) -> dict[str, Any]:
        record = self.get(record_id, project_id=project_id, account_id=account_id)
        return provenance_view(record)

    def list_visible(self, *, project_id: UUID, account_id: str) -> list[LearningRecord]:
        return self._records.list_visible(project_id=project_id, account_id=account_id)

    def retrieve(
        self,
        *,
        project_id: UUID,
        account_id: str,
        agent_id: str | None = None,
        task_type: str | None = None,
        element_type: str | None = None,
        learning_scope: LearningScope | None = None,
        limit: int = 20,
    ) -> LearningRetrieval:
        records = self._records.retrieve_approved(
            project_id=project_id,
            account_id=account_id,
            agent_id=_clean(agent_id),
            task_type=_clean(task_type),
            element_type=_clean(element_type),
            learning_scope=learning_scope.value if learning_scope is not None else None,
            limit=_clamp_limit(limit),
        )
        return LearningRetrieval(
            project_id=project_id,
            account_id=account_id,
            records=records,
            explanation=learning_explanation(records),
            authority=LEARNING_AUTHORITY,
            overrides_pem=False,
            overrides_rules=False,
            overrides_qa=False,
        )

    def record_use(
        self,
        *,
        project_id: UUID,
        task_id: UUID,
        retrieval: LearningRetrieval,
    ) -> None:
        if not retrieval.records:
            return
        self._records.record_uses(
            project_id=project_id,
            task_id=task_id,
            record_ids=[record.id for record in retrieval.records],
            explanation=retrieval.explanation,
        )

    def uses_for_task(
        self,
        *,
        project_id: UUID,
        task_id: UUID,
    ) -> list[dict[str, Any]]:
        return self._records.uses_for_task(project_id=project_id, task_id=task_id)

    def _decide(
        self,
        record_id: UUID,
        *,
        project_id: UUID,
        account_id: str,
        target: LearningApprovalStatus,
        reason: str | None = None,
    ) -> LearningRecord:
        record = self._require_visible(record_id, project_id=project_id, account_id=account_id)
        if not self._can_decide(record, project_id=project_id, account_id=account_id):
            raise LearningAuthorizationError(record_id)
        allowed = _DECISIONS[target]
        if record.approval_status not in allowed:
            raise LearningInvalidStateError(record_id, current_status=record.approval_status.value)
        provenance = dict(record.provenance)
        provenance["human_decision"] = target.value
        provenance["reviewed_by"] = account_id
        if reason:
            provenance["decision_reason"] = reason
        updated = self._records.save_decision(
            record_id,
            approval_status=target,
            reviewed_by=account_id,
            provenance=provenance,
        )
        if updated is None:
            raise LearningRecordNotFoundError(record_id, project_id=project_id)
        return updated

    def _require_visible(
        self,
        record_id: UUID,
        *,
        project_id: UUID,
        account_id: str,
    ) -> LearningRecord:
        record = self._records.get(record_id)
        if record is None or not self._is_visible(record, project_id=project_id, account_id=account_id):
            raise LearningRecordNotFoundError(record_id, project_id=project_id)
        return record

    def _is_visible(
        self,
        record: LearningRecord,
        *,
        project_id: UUID,
        account_id: str,
    ) -> bool:
        if record.learning_scope == LearningScope.PROJECT:
            return record.project_id == project_id
        if record.learning_scope == LearningScope.ENGINEER:
            return record.owner_account_id == account_id
        if record.learning_scope == LearningScope.GLOBAL:
            return (
                record.approval_status == LearningApprovalStatus.APPROVED
                or record.owner_account_id == account_id
            )
        return False

    def _can_decide(
        self,
        record: LearningRecord,
        *,
        project_id: UUID,
        account_id: str,
    ) -> bool:
        if record.learning_scope == LearningScope.PROJECT:
            return record.project_id == project_id
        return record.owner_account_id == account_id

    def _reject_unchecked_pass(self, context: dict[str, Any], validation_result: str) -> None:
        qa_status = context.get("qa_status")
        if qa_status == NOT_CHECKED and validation_result == "PASS":
            raise LearningSafetyError(
                "Learning cannot turn NOT_CHECKED into PASS.",
                details={"qa_status": NOT_CHECKED, "validation_result": validation_result},
            )


def _clamp_limit(limit: int) -> int:
    if limit < 1:
        return 1
    if limit > 50:
        return 50
    return limit
