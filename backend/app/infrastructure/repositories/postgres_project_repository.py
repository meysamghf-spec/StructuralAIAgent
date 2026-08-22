"""PostgreSQL implementation of ProjectRepository."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.project import Project
from app.infrastructure.database.connection import get_connection


class PostgresProjectRepository:
    def create(
        self,
        name: str,
        description: str | None = None,
        *,
        owner_account_id: str = "legacy",
    ) -> Project:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO projects (name, description, owner_account_id)
                    VALUES (%s, %s, %s)
                    RETURNING id, name, description, owner_account_id, created_at, updated_at
                    """,
                    (name, description, owner_account_id),
                )
                row = cur.fetchone()
        assert row is not None
        return Project.model_validate(row)

    def get_by_id(self, project_id: UUID) -> Project | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, description, owner_account_id, created_at, updated_at
                    FROM projects
                    WHERE id = %s
                    """,
                    (project_id,),
                )
                row = cur.fetchone()
        return Project.model_validate(row) if row else None

    def list_all(self) -> list[Project]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, description, owner_account_id, created_at, updated_at
                    FROM projects
                    ORDER BY created_at ASC
                    """
                )
                rows = cur.fetchall()
        return [Project.model_validate(row) for row in rows]

    def list_for_owner(self, owner_account_id: str) -> list[Project]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, description, owner_account_id, created_at, updated_at
                    FROM projects
                    WHERE owner_account_id = %s
                    ORDER BY created_at ASC
                    """,
                    (owner_account_id,),
                )
                rows = cur.fetchall()
        return [Project.model_validate(row) for row in rows]
