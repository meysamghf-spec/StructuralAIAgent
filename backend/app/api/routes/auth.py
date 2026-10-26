"""Authentication REST endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
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

SESSION_COOKIE = "saia_session"


def _set_session_cookie(response: Response, request: Request, token: str, *, remember: bool) -> None:
    """httpOnly session cookie: a browser session cookie, or 30 days (settings) when "remember me" is ticked."""
    from app.infrastructure.config import get_settings

    settings = get_settings()
    secure = (request.headers.get("x-forwarded-proto") or request.url.scheme) == "https"
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=secure, samesite="lax", path="/api/v1/auth",
        max_age=settings.auth_remember_expiry_hours * 3600 if remember else None,
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthTokenResponse)
def register_user(
    body: RegisterRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    user, token = auth_service.register_user(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
    )
    out = JSONResponse(
        AuthTokenResponse(access_token=token, user=UserResponse.from_domain(user)).model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
    )
    _set_session_cookie(out, request, token, remember=False)
    return out


@router.post("/login", response_model=AuthTokenResponse)
def login_user(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    user, token = auth_service.login(
        email=body.email, password=body.password, ip=_client_ip(request), remember=body.remember_me
    )
    payload = AuthTokenResponse(access_token=token, user=UserResponse.from_domain(user))
    out = JSONResponse(payload.model_dump(mode="json"))
    _set_session_cookie(out, request, token, remember=body.remember_me)
    return out


@router.post("/session", response_model=AuthTokenResponse)
def restore_session(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """Trade the httpOnly session cookie for a fresh bearer token (used when the browser has no stored token)."""
    from app.application.exceptions import AuthenticationError

    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        raise AuthenticationError("No active session")
    user, token, remember = auth_service.session_token(cookie)
    out = JSONResponse(AuthTokenResponse(access_token=token, user=UserResponse.from_domain(user)).model_dump(mode="json"))
    _set_session_cookie(out, request, token, remember=remember)
    return out


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user() -> Response:
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    out.delete_cookie(SESSION_COOKIE, path="/api/v1/auth")
    return out


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


def _request_host(request: Request) -> str:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    host = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0].lstrip("[")
    return host.lower()


def _ip_host(request: Request) -> bool:
    """True when the app is reached by a bare IP (no Google sign-in there: the redirect URI is the domain)."""
    import ipaddress

    host = _request_host(request)
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def google_config(request: Request) -> dict:
    from app.application.google_oauth import google_enabled
    from app.infrastructure.config import get_settings

    return {"enabled": google_enabled(get_settings()) and not _ip_host(request)}


def google_start(request: Request, next: str = "/") -> RedirectResponse:
    from app.application import google_oauth as g
    from app.application.exceptions import AuthenticationError
    from app.infrastructure.config import get_settings

    settings = get_settings()
    if not g.google_enabled(settings) or _ip_host(request):
        raise AuthenticationError("Google sign-in is not configured")
    if not next.startswith("/") or next.startswith("//"):
        next = "/"
    # The nonce cookie is host-only, and Google returns to the registered redirect URI's host. If sign-in was
    # started from another host (e.g. www), restart it on the callback host so cookie and callback match.
    from urllib.parse import urlparse

    cb = urlparse(settings.google_callback_url)
    host, cb_host = _request_host(request), (cb.hostname or "").lower()
    if host != cb_host and host.removeprefix("www.") == cb_host.removeprefix("www."):
        return RedirectResponse(f"{cb.scheme}://{cb.netloc}{request.url.path}?next={quote(next, safe="")}", status_code=302)
    nonce = g.new_nonce()
    state = g.make_state(AuthService(user_repository=None, settings=settings)._jwt_secret(), nonce, next)  # type: ignore[arg-type]
    resp = RedirectResponse(g.authorization_url(settings, state, nonce), status_code=302)
    resp.set_cookie(
        _GOOGLE_COOKIE, nonce, max_age=g.STATE_TTL_SECONDS, httponly=True, samesite="lax",
        secure=settings.google_callback_url.startswith("https://"), path="/api",
    )
    return resp


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
    resp.delete_cookie(_GOOGLE_COOKIE, path="/api")
    return resp


# Same handlers on /api/v1/auth/google/* and on /api/auth/google/* (the redirect URI registered with Google).
google_alias_router = APIRouter(prefix="/auth/google", tags=["auth"])
for _r in (router, google_alias_router):
    _p = "/google" if _r is router else ""
    _r.add_api_route(f"{_p}/config", google_config, methods=["GET"])
    _r.add_api_route(f"{_p}/start", google_start, methods=["GET"])
    _r.add_api_route(f"{_p}/callback", google_callback, methods=["GET"])
