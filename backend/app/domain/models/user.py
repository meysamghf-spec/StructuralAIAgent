"""User identity domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AuthMethod(StrEnum):
    LEGACY_ACTOR = "legacy_actor"
    BEARER_TOKEN = "bearer_token"


class User(BaseModel):
    id: UUID
    email: str
    password_hash: str
    display_name: str | None = None
    account_id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuthenticatedAccount(BaseModel):
    """Resolved caller identity for authorization and audit."""

    account_id: str
    auth_method: AuthMethod
    user_id: UUID | None = None
    email: str | None = None
    display_name: str | None = None
