"""Authentication REST endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from urllib.parse import quote

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


# ---- Sign in with Google -------------------------------------------------
_GOOGLE_COOKIE = "sa_google_nonce"


@router.get("/google/config")
def google_config() -> dict:
    from app.application.google_oauth import google_enabled
    from app.infrastructure.config import get_settings

    return {"enabled": google_enabled(get_settings())}


@router.get("/google/start")
def google_start(request: Request, next: str = "/") -> RedirectResponse:
    from app.application import google_oauth as g
    from app.application.exceptions import AuthenticationError
    from app.infrastructure.config import get_settings

    settings = get_settings()
    if not g.google_enabled(settings):
        raise AuthenticationError("Google sign-in is not configured")
    if not next.startswith("/") or next.startswith("//"):
        next = "/"
    nonce = g.new_nonce()
    state = g.make_state(AuthService(user_repository=None, settings=settings)._jwt_secret(), nonce, next)  # type: ignore[arg-type]
    resp = RedirectResponse(g.authorization_url(settings, state, nonce), status_code=302)
    resp.set_cookie(
        _GOOGLE_COOKIE, nonce, max_age=g.STATE_TTL_SECONDS, httponly=True, samesite="lax",
        secure=(settings.google_redirect_uri or "").startswith("https://"), path="/api/v1/auth/google",
    )
    return resp


@router.get("/google/callback")
def google_callback(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    from app.application import google_oauth as g
    from app.application.exceptions import ApplicationError
    from app.infrastructure.config import get_settings

    settings = get_settings()
    target = g.post_login_url(settings)
    try:
        if not g.google_enabled(settings):
            raise ValueError("Google sign-in is not configured")
        if error or not code or not state:
            raise ValueError(error or "Google sign-in was cancelled")
        data = g.read_state(auth_service._jwt_secret(), state, request.cookies.get(_GOOGLE_COOKIE))
        claims = g.exchange_code(settings, code, data["n"])
        _user, token = auth_service.login_with_google(email=claims["email"], display_name=claims.get("name"))
        resp = RedirectResponse(f"{target}#google_token={quote(token)}&next={quote(data.get('p', '/'))}", status_code=302)
    except (ApplicationError, ValueError) as exc:
        resp = RedirectResponse(f"{target}#google_error={quote(str(exc))}", status_code=302)
    resp.delete_cookie(_GOOGLE_COOKIE, path="/api/v1/auth/google")
    return resp
