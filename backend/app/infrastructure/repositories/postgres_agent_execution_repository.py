"""PostgreSQL implementation of AgentExecutionRepository."""

from __future__ import annotations

import json
from uuid import UUID

from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
)
from app.infrastructure.database.connection import get_connection

_AGENT_EXECUTION_COLUMNS = """
    id, project_id, agent_definition_id, agent_version,
    execution_status, input_request, context_snapshot,
    output, agent_result, validation_status, traceability_metadata,
    prompt_generation, approval_request_id, error_metadata,
    started_at, completed_at, created_by, created_at, updated_at
"""


def _row_to_record(row: dict) -> AgentExecutionRecord:
    payload = dict(row)
    payload["execution_status"] = AgentExecutionStatus(payload["execution_status"])
    if payload.get("validation_status"):
        payload["validation_status"] = AgentValidationStatus(payload["validation_status"])
    if payload.get("agent_result") and isinstance(payload["agent_result"], dict):
        payload["agent_result"] = AgentResult.model_validate(payload["agent_result"])
    return AgentExecutionRecord.model_validate(payload)


class PostgresAgentExecutionRepository:
    def create(
        self,
        *,
        project_id: UUID,
        agent_definition_id: UUID,
        agent_version: int,
        input_request: dict,
        context_snapshot: dict,
        created_by: str | None = None,
    ) -> AgentExecutionRecord:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO agent_executions (
                        project_id,
                        agent_definition_id,
                        agent_version,
                        execution_status,
                        input_request,
                        context_snapshot,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                    RETURNING {_AGENT_EXECUTION_COLUMNS}
                    """,
                    (
                        project_id,
                        agent_definition_id,
                        agent_version,
                        AgentExecutionStatus.CREATED.value,
                        json.dumps(input_request),
                        json.dumps(context_snapshot),
                        created_by,
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        return _row_to_record(row)

    def get_by_id(self, execution_id: UUID) -> AgentExecutionRecord | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_AGENT_EXECUTION_COLUMNS}
                    FROM agent_executions
                    WHERE id = %s
                    """,
                    (execution_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_record(row)

    def update(self, record: AgentExecutionRecord) -> AgentExecutionRecord:
        agent_result_payload = (
            record.agent_result.model_dump() if record.agent_result is not None else None
        )
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE agent_executions
                    SET
                        execution_status = %s,
                        input_request = %s::jsonb,
                        context_snapshot = %s::jsonb,
                        output = %s::jsonb,
                        agent_result = %s::jsonb,
                        validation_status = %s,
                        traceability_metadata = %s::jsonb,
                        prompt_generation = %s::jsonb,
                        approval_request_id = %s,
                        error_metadata = %s::jsonb,
                        started_at = %s,
                        completed_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING {_AGENT_EXECUTION_COLUMNS}
                    """,
                    (
                        record.execution_status.value,
                        json.dumps(record.input_request),
                        json.dumps(record.context_snapshot),
                        json.dumps(record.output) if record.output is not None else None,
                        json.dumps(agent_result_payload) if agent_result_payload else None,
                        record.validation_status.value if record.validation_status else None,
                        json.dumps(record.traceability_metadata),
                        json.dumps(record.prompt_generation)
                        if record.prompt_generation is not None
                        else None,
                        record.approval_request_id,
                        json.dumps(record.error_metadata),
                        record.started_at,
                        record.completed_at,
                        record.id,
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        return _row_to_record(row)

    def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 100,
    ) -> list[AgentExecutionRecord]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_AGENT_EXECUTION_COLUMNS}
                    FROM agent_executions
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (project_id, limit),
                )
                rows = cur.fetchall()
        return [_row_to_record(row) for row in rows]
