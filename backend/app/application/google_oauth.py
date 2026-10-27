"""Sign in with Google: OAuth 2.0 authorization-code flow with PKCE (S256) and OpenID Connect id_token checks.

Server-side only. The browser is redirected to Google and back to our registered redirect URI; the token exchange
(server -> oauth2.googleapis.com) happens here, optionally through ``GOOGLE_OAUTH_PROXY``. Nothing secret is logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode, urlparse

import httpx

from app.infrastructure.config import Settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
STATE_TTL_SECONDS = 600
CLOCK_SKEW_SECONDS = 120

# Error codes put in the login redirect (#google_error=<code>); the frontend maps them to Persian/English text.
ERROR_CODES = (
    "not_configured", "cancelled", "state", "token_exchange", "unreachable", "token_invalid",
    "email_unverified", "account_disabled", "failed",
)


class GoogleSignInError(Exception):
    """A Google sign-in failure with a stable, user-safe ``code`` (never carries provider or secret details)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code if code in ERROR_CODES else "failed"


def google_enabled(settings: Settings) -> bool:
    """Off by default: needs GOOGLE_OAUTH_ENABLED=true plus a client id and secret."""
    return bool(
        settings.google_oauth_enabled
        and settings.google_client_id
        and settings.google_client_secret
        and settings.google_client_secret.get_secret_value()
    )


def post_login_url(settings: Settings) -> str:
    if settings.google_post_login_url:
        return settings.google_post_login_url
    u = urlparse(settings.google_callback_url)
    return f"{u.scheme}://{u.netloc}/login"


def safe_next(path: str | None) -> str:
    """Only same-site absolute paths (no scheme-relative or backslash tricks)."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path or "\n" in path or "\r" in path:
        return "/"
    return path[:512]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sign(secret: str, payload: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def make_state(secret: str, nonce: str, next_path: str, remember: bool = False) -> str:
    payload = _b64(
        json.dumps({"n": nonce, "x": int(time.time()) + STATE_TTL_SECONDS, "p": next_path, "r": 1 if remember else 0}).encode()
    )
    return f"{payload}.{_sign(secret, payload)}"


def read_state(secret: str, state: str, cookie_nonce: str | None) -> dict:
    """Verify the signed state (HMAC, expiry) and that it belongs to this browser (nonce cookie)."""
    try:
        payload, sig = state.split(".", 1)
        if not hmac.compare_digest(sig, _sign(secret, payload)):
            raise ValueError("bad signature")
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if not isinstance(data, dict):
            raise ValueError("bad payload")
    except (ValueError, TypeError) as exc:
        raise GoogleSignInError("state") from exc
    if int(data.get("x", 0)) < time.time():
        raise GoogleSignInError("state")
    if not cookie_nonce or not hmac.compare_digest(cookie_nonce, str(data.get("n", ""))):
        raise GoogleSignInError("state")
    return data


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def code_verifier(secret: str, nonce: str) -> str:
    """PKCE verifier derived from the per-login nonce and the server secret (no extra cookie, never sent to the browser)."""
    return _b64(hmac.new(secret.encode(), b"pkce:" + nonce.encode(), hashlib.sha256).digest())


def code_challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode()).digest())


def authorization_url(settings: Settings, state: str, nonce: str, verifier: str) -> str:
    return AUTH_URL + "?" + urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_callback_url,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge(verifier),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )


def _http_client(settings: Settings) -> httpx.Client:
    proxy = settings.google_oauth_proxy.get_secret_value() if settings.google_oauth_proxy else None
    return httpx.Client(timeout=settings.google_oauth_timeout_seconds, proxy=proxy or None)


def exchange_code(settings: Settings, code: str, nonce: str, verifier: str) -> dict:
    """Exchange the authorization code (with the PKCE verifier) and return the validated id_token claims."""
    assert settings.google_client_secret is not None
    try:
        with _http_client(settings) as client:
            tok = client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret.get_secret_value(),
                    "redirect_uri": settings.google_callback_url,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
    except httpx.HTTPError as exc:  # timeout / DNS / refused / proxy failure: the server cannot reach Google
        raise GoogleSignInError("unreachable") from exc
    if tok.status_code != 200:
        raise GoogleSignInError("token_exchange")
    try:
        id_token = tok.json().get("id_token")
    except ValueError as exc:
        raise GoogleSignInError("token_exchange") from exc
    if not id_token:
        raise GoogleSignInError("token_exchange")
    return validate_claims(settings, decode_id_token_payload(id_token), nonce)


def decode_id_token_payload(id_token: str) -> dict:
    """Read the id_token claims. The token came straight from Google's token endpoint over TLS, so (OIDC Core
    3.1.3.7) the signature check may be skipped; every claim that matters is validated in ``validate_claims``."""
    try:
        part = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (IndexError, ValueError, TypeError) as exc:
        raise GoogleSignInError("token_invalid") from exc
    if not isinstance(claims, dict):
        raise GoogleSignInError("token_invalid")
    return claims


def validate_claims(settings: Settings, claims: dict, nonce: str) -> dict:
    aud = claims.get("aud")
    auds = aud if isinstance(aud, list) else [aud]
    if settings.google_client_id not in auds or (len(auds) > 1 and claims.get("azp") != settings.google_client_id):
        raise GoogleSignInError("token_invalid")
    if claims.get("iss") not in VALID_ISSUERS:
        raise GoogleSignInError("token_invalid")
    try:
        exp = int(claims.get("exp", 0))
    except (TypeError, ValueError) as exc:
        raise GoogleSignInError("token_invalid") from exc
    if exp + CLOCK_SKEW_SECONDS < time.time():
        raise GoogleSignInError("token_invalid")
    if not claims.get("sub") or not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(claims["nonce"], nonce):
        raise GoogleSignInError("token_invalid")
    verified = claims.get("email_verified")
    if not (verified is True or str(verified).lower() == "true") or not claims.get("email"):
        raise GoogleSignInError("email_unverified")
    return claims
