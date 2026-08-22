"""Authentication REST endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_current_account, get_entitlement_authorization_service
from app.api.schemas.auth import (
    AuthTokenResponse,
    FeatureAccessEntryResponse,
    FeatureAccessSummaryResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.application.auth_service import AuthService
from app.application.entitlement_authorization_service import EntitlementAuthorizationService
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthTokenResponse)
def register_user(
    body: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthTokenResponse:
    user, token = auth_service.register_user(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
    )
    return AuthTokenResponse(access_token=token, user=UserResponse.from_domain(user))


@router.post("/login", response_model=AuthTokenResponse)
def login_user(
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthTokenResponse:
    user, token = auth_service.login(email=body.email, password=body.password)
    return AuthTokenResponse(access_token=token, user=UserResponse.from_domain(user))


@router.get("/me", response_model=UserResponse)
def get_current_user(
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    if account.user_id is None:
        from app.application.exceptions import AuthenticationError

        raise AuthenticationError("Bearer authentication is required for /auth/me")
    user = auth_service.get_user(account.user_id)
    return UserResponse.from_domain(user)


@router.get("/me/features", response_model=FeatureAccessSummaryResponse)
def get_current_user_features(
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    entitlements: Annotated[
        EntitlementAuthorizationService, Depends(get_entitlement_authorization_service)
    ],
) -> FeatureAccessSummaryResponse:
    summary = entitlements.summarize_account_features(account.account_id)
    return FeatureAccessSummaryResponse(
        features={
            key: FeatureAccessEntryResponse.model_validate(value) for key, value in summary.items()
        }
    )
