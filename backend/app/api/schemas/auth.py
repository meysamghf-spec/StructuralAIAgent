"""Authentication API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.user import User


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


class UserResponse(BaseModel):
    id: UUID
    email: str
    account_id: str
    display_name: str | None = None

    @classmethod
    def from_domain(cls, user: User) -> UserResponse:
        return cls(
            id=user.id,
            email=user.email,
            account_id=user.account_id,
            display_name=user.display_name,
        )


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class FeatureAccessEntryResponse(BaseModel):
    available: bool
    reason: str
    upgrade_product_id: str | None = None
    product_name: str | None = None
    entitlement_status: str | None = None
    expires_at: str | None = None


class FeatureAccessSummaryResponse(BaseModel):
    features: dict[str, FeatureAccessEntryResponse]
