"""PostgreSQL persistence for engineering learning records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.models.engineering_learning import (
    LearningApprovalStatus,
    LearningRecord,
    LearningScope,
)
from app.infrastructure.database.connection import get_connection

_COLUMNS = """
    id,
    project_id,
    owner_account_id,
    agent_id,
    task_id,
    source_snapshot_id,
    source_element_ids,
    source_element_type,
    input_context,
    agent_output,
    human_correction,
    engineering_reason,
    validation_result,
    approval_status,
    learning_scope,
    applicability,
    confidence,
    provenance,
    reviewed_by,
    reviewed_at,
    created_at,
    updated_at
"""


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {})


def _load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        parsed = json.loads(value)
        return default if parsed is None else parsed
    return value


def _record(row: dict[str, Any]) -> LearningRecord:
    payload = dict(row)
    payload["source_element_ids"] = [str(item) for item in _load(row["source_element_ids"], [])]
    payload["input_context"] = _load(row["input_context"], {})
    payload["agent_output"] = _load(row["agent_output"], {})
    correction = _load(row["human_correction"], None)
    payload["human_correction"] = correction if isinstance(correction, dict) else None
    payload["applicability"] = _load(row["applicability"], {})
    payload["provenance"] = _load(row["provenance"], {})
    payload["approval_status"] = LearningApprovalStatus(row["approval_status"])
    payload["learning_scope"] = LearningScope(row["learning_scope"])
    return LearningRecord.model_validate(payload)


class PostgresEngineeringLearningRepository:
    def create(self, record: LearningRecord) -> LearningRecord:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO engineering_learning_records (
                        id, project_id, owner_account_id, agent_id, task_id,
                        source_snapshot_id, source_element_ids, source_element_type,
                        input_context, agent_output, human_correction, engineering_reason,
                        validation_result, approval_status, learning_scope, applicability,
                        confidence, provenance
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s::jsonb, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s,
                        %s, %s, %s, %s::jsonb,
                        %s, %s::jsonb
                    )
                    RETURNING {_COLUMNS}
                    """,
                    (
                        record.id,
                        record.project_id,
                        record.owner_account_id,
                        record.agent_id,
                        record.task_id,
                        record.source_snapshot_id,
                        _json(record.source_element_ids),
                        record.source_element_type,
                        _json(record.input_context),
                        _json(record.agent_output),
                        _json(record.human_correction) if record.human_correction is not None else None,
                        record.engineering_reason,
                        record.validation_result,
                        record.approval_status.value,
                        record.learning_scope.value,
                        _json(record.applicability),
                        record.confidence,
                        _json(record.provenance),
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        return _record(row)

    def get(self, record_id: UUID) -> LearningRecord | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_COLUMNS} FROM engineering_learning_records WHERE id = %s",
                    (record_id,),
                )
                row = cur.fetchone()
        return _record(row) if row else None

    def save_decision(
        self,
        record_id: UUID,
        *,
        approval_status: LearningApprovalStatus,
        reviewed_by: str,
        provenance: dict[str, Any],
    ) -> LearningRecord | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE engineering_learning_records
                    SET approval_status = %s,
                        reviewed_by = %s,
                        reviewed_at = %s,
                        provenance = %s::jsonb,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING {_COLUMNS}
                    """,
                    (
                        approval_status.value,
                        reviewed_by,
                        datetime.now(UTC),
                        _json(provenance),
                        datetime.now(UTC),
                        record_id,
                    ),
                )
                row = cur.fetchone()
        return _record(row) if row else None

    def list_visible(self, *, project_id: UUID, account_id: str) -> list[LearningRecord]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_COLUMNS}
                    FROM engineering_learning_records
                    WHERE (
                        learning_scope = 'PROJECT' AND project_id = %s
                    ) OR (
                        learning_scope = 'ENGINEER' AND owner_account_id = %s
                    ) OR (
                        learning_scope = 'GLOBAL'
                        AND (approval_status = 'APPROVED' OR owner_account_id = %s)
                    )
                    ORDER BY created_at DESC, id DESC
                    """,
                    (project_id, account_id, account_id),
                )
                rows = cur.fetchall()
        return [_record(row) for row in rows]

    def retrieve_approved(
        self,
        *,
        project_id: UUID,
        account_id: str,
        agent_id: str | None,
        task_type: str | None,
        element_type: str | None,
        learning_scope: str | None,
        analysis_type: str | None = None,
        design_type: str | None = None,
        apply_operation: bool = False,
        limit: int = 20,
    ) -> list[LearningRecord]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_COLUMNS}
                    FROM engineering_learning_records
                    WHERE approval_status = 'APPROVED'
                      AND (
                            (learning_scope = 'PROJECT' AND project_id = %s)
                         OR (learning_scope = 'ENGINEER' AND owner_account_id = %s)
                         OR (learning_scope = 'GLOBAL')
                      )
                      AND (%s::varchar IS NULL OR learning_scope = %s)
                      AND (%s::varchar IS NULL OR agent_id IS NULL OR agent_id = %s)
                      AND (%s::varchar IS NULL OR source_element_type IS NULL OR source_element_type = %s)
                      AND (
                            %s::varchar IS NULL
                         OR applicability->>'task_type' IS NULL
                         OR applicability->>'task_type' = %s
                      )
                      AND (
                            %s::boolean IS FALSE
                         OR (
                              (
                                applicability->>'task_type' IS NULL
                                OR applicability->>'task_type' = %s
                                OR applicability->>'task_type' = %s
                                OR applicability->>'task_type' = %s
                              )
                          AND (
                                applicability->>'analysis_type' IS NULL
                                OR applicability->>'analysis_type' = %s
                              )
                          AND (
                                applicability->>'design_type' IS NULL
                                OR applicability->>'design_type' = %s
                              )
                            )
                      )
                    ORDER BY created_at ASC, id ASC
                    LIMIT %s
                    """,
                    (
                        project_id,
                        account_id,
                        learning_scope,
                        learning_scope,
                        agent_id,
                        agent_id,
                        element_type,
                        element_type,
                        task_type,
                        task_type,
                        apply_operation,
                        task_type,
                        analysis_type,
                        design_type,
                        analysis_type,
                        design_type,
                        limit,
                    ),
                )
                rows = cur.fetchall()
        return [_record(row) for row in rows]

    def record_uses(
        self,
        *,
        project_id: UUID,
        task_id: UUID,
        record_ids: list[UUID],
        explanation: str,
    ) -> None:
        if not record_ids:
            return
        with get_connection() as conn:
            with conn.cursor() as cur:
                for record_id in record_ids:
                    cur.execute(
                        """
                        INSERT INTO engineering_learning_uses (
                            learning_record_id, project_id, task_id, explanation
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (record_id, project_id, task_id, explanation),
                    )

    def uses_for_task(self, *, project_id: UUID, task_id: UUID) -> list[dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT learning_record_id, explanation, created_at
                    FROM engineering_learning_uses
                    WHERE project_id = %s AND task_id = %s
                    ORDER BY created_at ASC, learning_record_id ASC
                    """,
                    (project_id, task_id),
                )
                rows = cur.fetchall()
        return [
            {
                "learning_record_id": str(row["learning_record_id"]),
                "explanation": row["explanation"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
