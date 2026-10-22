"""Sign in with Google (OAuth 2.0 authorization-code flow + OIDC id_token checks)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode, urlparse

import httpx

from app.application.exceptions import AuthenticationError
from app.infrastructure.config import Settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
STATE_TTL_SECONDS = 600


def google_enabled(settings: Settings) -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_client_secret.get_secret_value()
        and settings.google_redirect_uri
    )


def post_login_url(settings: Settings) -> str:
    if settings.google_post_login_url:
        return settings.google_post_login_url
    u = urlparse(settings.google_redirect_uri or "")
    return f"{u.scheme}://{u.netloc}/login"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def make_state(secret: str, nonce: str, next_path: str) -> str:
    payload = _b64(json.dumps({"n": nonce, "x": int(time.time()) + STATE_TTL_SECONDS, "p": next_path}).encode())
    sig = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_state(secret: str, state: str, cookie_nonce: str | None) -> dict:
    try:
        payload, sig = state.split(".", 1)
    except ValueError as exc:
        raise AuthenticationError("Invalid Google sign-in state") from exc
    expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise AuthenticationError("Invalid Google sign-in state")
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    if data.get("x", 0) < time.time():
        raise AuthenticationError("Google sign-in expired, please try again")
    if not cookie_nonce or not hmac.compare_digest(cookie_nonce, data.get("n", "")):
        raise AuthenticationError("Google sign-in state mismatch")
    return data


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def authorization_url(settings: Settings, state: str, nonce: str) -> str:
    return AUTH_URL + "?" + urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        }
    )


def exchange_code(settings: Settings, code: str, nonce: str) -> dict:
    """Exchange the code and return verified id_token claims (email, name)."""
    assert settings.google_client_secret is not None
    with httpx.Client(timeout=15) as client:
        tok = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if tok.status_code != 200:
            raise AuthenticationError("Google token exchange failed")
        id_token = tok.json().get("id_token")
        if not id_token:
            raise AuthenticationError("Google did not return an id_token")
        info = client.get(TOKENINFO_URL, params={"id_token": id_token})
        if info.status_code != 200:
            raise AuthenticationError("Google id_token is invalid")
        claims = info.json()
    return validate_claims(settings, claims, nonce)


def validate_claims(settings: Settings, claims: dict, nonce: str) -> dict:
    if claims.get("aud") != settings.google_client_id:
        raise AuthenticationError("Google id_token audience mismatch")
    if claims.get("iss") not in VALID_ISSUERS:
        raise AuthenticationError("Google id_token issuer mismatch")
    if int(claims.get("exp", 0)) < time.time():
        raise AuthenticationError("Google id_token expired")
    if claims.get("nonce") != nonce:
        raise AuthenticationError("Google id_token nonce mismatch")
    if str(claims.get("email_verified")).lower() != "true" or not claims.get("email"):
        raise AuthenticationError("Google account email is not verified")
    return claims
