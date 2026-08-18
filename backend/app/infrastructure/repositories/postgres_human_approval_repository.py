"""PostgreSQL implementation of HumanApprovalRepository."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from app.domain.models.human_approval import (
    ApprovalEvent,
    ApprovalEventType,
    ApprovalStatus,
    ApprovalTargetType,
    HumanApprovalRequest,
)
from app.infrastructure.database.connection import get_connection


class PostgresHumanApprovalRepository:
    def create_request(
        self,
        project_id: UUID,
        *,
        requester: str,
        target_type: ApprovalTargetType,
        target_action: str,
        summary: str,
        target_object_type: str | None = None,
        target_object_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> HumanApprovalRequest:
        metadata_payload = metadata or {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO human_approval_requests (
                        project_id,
                        requester,
                        target_type,
                        target_action,
                        target_object_type,
                        target_object_id,
                        summary,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING
                        id,
                        project_id,
                        requester,
                        target_type,
                        target_action,
                        target_object_type,
                        target_object_id,
                        summary,
                        status,
                        approver,
                        decision,
                        rejection_reason,
                        metadata,
                        requested_at,
                        resolved_at,
                        created_at,
                        updated_at
                    """,
                    (
                        project_id,
                        requester,
                        target_type.value,
                        target_action,
                        target_object_type,
                        target_object_id,
                        summary,
                        json.dumps(metadata_payload),
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_request(row)

    def get_request(
        self,
        project_id: UUID,
        request_id: UUID,
    ) -> HumanApprovalRequest | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        requester,
                        target_type,
                        target_action,
                        target_object_type,
                        target_object_id,
                        summary,
                        status,
                        approver,
                        decision,
                        rejection_reason,
                        metadata,
                        requested_at,
                        resolved_at,
                        created_at,
                        updated_at
                    FROM human_approval_requests
                    WHERE project_id = %s
                      AND id = %s
                    """,
                    (project_id, request_id),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_request(row)

    def list_requests(
        self,
        project_id: UUID,
        *,
        status: ApprovalStatus | None = None,
    ) -> list[HumanApprovalRequest]:
        conditions = ["project_id = %s"]
        params: list[object] = [project_id]

        if status is not None:
            conditions.append("status = %s")
            params.append(status.value)

        where_clause = " AND ".join(conditions)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        id,
                        project_id,
                        requester,
                        target_type,
                        target_action,
                        target_object_type,
                        target_object_id,
                        summary,
                        status,
                        approver,
                        decision,
                        rejection_reason,
                        metadata,
                        requested_at,
                        resolved_at,
                        created_at,
                        updated_at
                    FROM human_approval_requests
                    WHERE {where_clause}
                    ORDER BY requested_at DESC
                    """,
                    params,
                )
                rows = cur.fetchall()

        return [self._row_to_request(row) for row in rows]

    def update_request(
        self,
        project_id: UUID,
        request_id: UUID,
        *,
        status: ApprovalStatus,
        approver: str | None = None,
        decision: ApprovalStatus | None = None,
        rejection_reason: str | None = None,
        resolved_at: datetime | None = None,
    ) -> HumanApprovalRequest | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE human_approval_requests
                    SET
                        status = %s,
                        approver = %s,
                        decision = %s,
                        rejection_reason = %s,
                        resolved_at = %s,
                        updated_at = NOW()
                    WHERE project_id = %s
                      AND id = %s
                    RETURNING
                        id,
                        project_id,
                        requester,
                        target_type,
                        target_action,
                        target_object_type,
                        target_object_id,
                        summary,
                        status,
                        approver,
                        decision,
                        rejection_reason,
                        metadata,
                        requested_at,
                        resolved_at,
                        created_at,
                        updated_at
                    """,
                    (
                        status.value,
                        approver,
                        decision.value if decision is not None else None,
                        rejection_reason,
                        resolved_at,
                        project_id,
                        request_id,
                    ),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return self._row_to_request(row)

    def create_event(
        self,
        project_id: UUID,
        approval_request_id: UUID,
        *,
        event_type: ApprovalEventType,
        actor: str,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> ApprovalEvent:
        metadata_payload = metadata or {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO human_approval_events (
                        approval_request_id,
                        project_id,
                        event_type,
                        actor,
                        reason,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING
                        id,
                        approval_request_id,
                        project_id,
                        event_type,
                        actor,
                        reason,
                        metadata,
                        created_at
                    """,
                    (
                        approval_request_id,
                        project_id,
                        event_type.value,
                        actor,
                        reason,
                        json.dumps(metadata_payload),
                    ),
                )
                row = cur.fetchone()

        assert row is not None
        return self._row_to_event(row)

    def list_events(
        self,
        project_id: UUID,
        *,
        approval_request_id: UUID | None = None,
    ) -> list[ApprovalEvent]:
        conditions = ["project_id = %s"]
        params: list[object] = [project_id]

        if approval_request_id is not None:
            conditions.append("approval_request_id = %s")
            params.append(approval_request_id)

        where_clause = " AND ".join(conditions)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        id,
                        approval_request_id,
                        project_id,
                        event_type,
                        actor,
                        reason,
                        metadata,
                        created_at
                    FROM human_approval_events
                    WHERE {where_clause}
                    ORDER BY created_at ASC
                    """,
                    params,
                )
                rows = cur.fetchall()

        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_request(row: dict) -> HumanApprovalRequest:
        row["target_type"] = ApprovalTargetType(row["target_type"])
        row["status"] = ApprovalStatus(row["status"])
        row["decision"] = ApprovalStatus(row["decision"]) if row.get("decision") else None
        return HumanApprovalRequest.model_validate(row)

    @staticmethod
    def _row_to_event(row: dict) -> ApprovalEvent:
        row["event_type"] = ApprovalEventType(row["event_type"])
        return ApprovalEvent.model_validate(row)
