"""PostgreSQL user repository."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.user import User
from app.infrastructure.database.connection import get_connection


class PostgresUserRepository:
    def create(
        self,
        *,
        email: str,
        password_hash: str,
        account_id: str,
        display_name: str | None = None,
    ) -> User:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, account_id, display_name)
                    VALUES (%s, %s, %s, %s)
                    RETURNING
                        id,
                        email,
                        password_hash,
                        display_name,
                        account_id,
                        is_active,
                        created_at,
                        updated_at
                    """,
                    (email.lower(), password_hash, account_id, display_name),
                )
                row = cur.fetchone()
        assert row is not None
        return User.model_validate(row)

    def get_by_email(self, email: str) -> User | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        email,
                        password_hash,
                        display_name,
                        account_id,
                        is_active,
                        created_at,
                        updated_at
                    FROM users
                    WHERE email = %s
                    """,
                    (email.lower(),),
                )
                row = cur.fetchone()
        return User.model_validate(row) if row else None

    def get_by_id(self, user_id: UUID) -> User | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        email,
                        password_hash,
                        display_name,
                        account_id,
                        is_active,
                        created_at,
                        updated_at
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        return User.model_validate(row) if row else None

    def get_by_account_id(self, account_id: str) -> User | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        email,
                        password_hash,
                        display_name,
                        account_id,
                        is_active,
                        created_at,
                        updated_at
                    FROM users
                    WHERE account_id = %s
                    """,
                    (account_id,),
                )
                row = cur.fetchone()
        return User.model_validate(row) if row else None
