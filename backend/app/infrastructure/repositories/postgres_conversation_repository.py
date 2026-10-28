"""PostgreSQL persistence for conversations and messages."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.models.conversation import (
    Conversation,
    ConversationMessage,
    MessageAttachment,
    MessageRole,
)
from app.infrastructure.database.connection import get_connection


class PostgresConversationRepository:
    def create(
        self,
        *,
        account_id: str,
        title: str,
        project_id: UUID | None = None,
    ) -> Conversation:
        conversation_id = uuid4()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (id, account_id, project_id, title)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, account_id, project_id, title, created_at, updated_at
                    """,
                    (conversation_id, account_id, project_id, title),
                )
                row = cur.fetchone()
        assert row is not None
        return Conversation.model_validate(row)

    def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, account_id, project_id, title, created_at, updated_at
                    FROM conversations
                    WHERE id = %s
                    """,
                    (conversation_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return Conversation.model_validate(row)

    def list_for_account(
        self,
        account_id: str,
        *,
        limit: int = 100,
        project_id: UUID | None = None,
        unassigned: bool = False,
    ) -> list[Conversation]:
        """Account conversations, newest first. ``project_id`` keeps one project's chats; ``unassigned`` keeps chats with no project."""
        where = "account_id = %s"
        params: list = [account_id]
        if project_id is not None:
            where += " AND project_id = %s"
            params.append(project_id)
        elif unassigned:
            where += " AND project_id IS NULL"
        params.append(limit)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, account_id, project_id, title, created_at, updated_at
                    FROM conversations
                    WHERE {where}
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        return [Conversation.model_validate(row) for row in rows]

    def update_title(self, conversation_id: UUID, title: str) -> Conversation | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE conversations
                    SET title = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, account_id, project_id, title, created_at, updated_at
                    """,
                    (title, conversation_id),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return Conversation.model_validate(row)

    def touch_updated_at(self, conversation_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                    (conversation_id,),
                )

    def set_project(self, conversation_id: UUID, project_id: UUID) -> Conversation | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE conversations
                    SET project_id = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, account_id, project_id, title, created_at, updated_at
                    """,
                    (project_id, conversation_id),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return Conversation.model_validate(row)

    def delete(self, conversation_id: UUID) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
                return cur.rowcount > 0

    def create_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        attachments: list[MessageAttachment] | None = None,
        metadata: dict | None = None,
    ) -> ConversationMessage:
        message_id = uuid4()
        attachments_payload = [item.model_dump(mode="json") for item in (attachments or [])]
        metadata_payload = metadata or {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversation_messages (
                        id, conversation_id, role, content, attachments, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    RETURNING id, conversation_id, role, content, attachments, metadata, created_at
                    """,
                    (
                        message_id,
                        conversation_id,
                        role.value,
                        content,
                        json.dumps(attachments_payload),
                        json.dumps(metadata_payload),
                    ),
                )
                row = cur.fetchone()
        assert row is not None
        return _row_to_message(row)

    def list_messages(
        self,
        conversation_id: UUID,
        *,
        limit: int = 500,
    ) -> list[ConversationMessage]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, conversation_id, role, content, attachments, metadata, created_at
                    FROM conversation_messages
                    WHERE conversation_id = %s
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (conversation_id, limit),
                )
                rows = cur.fetchall()
        return [_row_to_message(row) for row in rows]


def _row_to_message(row: dict) -> ConversationMessage:
    attachments_raw = row.get("attachments") or []
    if isinstance(attachments_raw, str):
        attachments_raw = json.loads(attachments_raw)
    metadata_raw = row.get("metadata") or {}
    if isinstance(metadata_raw, str):
        metadata_raw = json.loads(metadata_raw)
    attachments = [MessageAttachment.model_validate(item) for item in attachments_raw]
    return ConversationMessage(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=MessageRole(row["role"]),
        content=row["content"],
        attachments=attachments,
        metadata=metadata_raw,
        created_at=row["created_at"],
    )
