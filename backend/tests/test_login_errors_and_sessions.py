"""Login: specific error reasons, rate limiting, "remember me" cookie sessions and the Google config gate."""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.application.login_throttle import LoginThrottle, login_throttle
from app.infrastructure.config import get_settings


@pytest.fixture(autouse=True)
def _fresh_throttle():
    login_throttle.reset()
    yield
    login_throttle.reset()


def _register(client: TestClient) -> tuple[str, str]:
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "secure-password"})
    assert r.status_code == 201
    return email, "secure-password"


def _login(client, email, password, **extra):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password, **extra})


def test_login_reports_the_specific_reason(api_client: TestClient):
    email, pw = _register(api_client)
    bad_format = _login(api_client, "not-an-email", pw)
    assert bad_format.status_code == 422 and bad_format.json()["error"]["code"] == "INVALID_EMAIL"
    unknown = _login(api_client, f"nobody-{uuid.uuid4().hex[:6]}@example.com", pw)
    assert unknown.status_code == 401 and unknown.json()["error"]["code"] == "EMAIL_NOT_REGISTERED"
    wrong = _login(api_client, email, "totally-wrong")
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "WRONG_PASSWORD"
    assert wrong.json()["error"]["details"]["attempts_left"] == 4
    short = _login(api_client, email, "x")  # a short wrong password is a wrong password, not a validation error
    assert short.json()["error"]["code"] == "WRONG_PASSWORD"
    assert _login(api_client, email, pw).status_code == 200


def test_repeated_failures_lock_with_retry_after(api_client: TestClient):
    email, pw = _register(api_client)
    codes = [_login(api_client, email, "wrong-pass-1").json()["error"]["code"] for _ in range(5)]
    assert codes[:4] == ["WRONG_PASSWORD"] * 4 and codes[4] == "RATE_LIMITED"
    locked = _login(api_client, email, pw)  # even the right password is refused while locked
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "RATE_LIMITED"
    assert int(locked.headers["retry-after"]) > 0 and locked.json()["error"]["details"]["retry_after_seconds"] > 0


def test_throttle_window_and_reset():
    t = LoginThrottle()
    now = 1000.0
    for i in range(3):
        left = t.failure("a@b.c", "1.1.1.1", limit=3, lockout=60, now=now + i)
    assert left is None and t.retry_after("a@b.c", "1.1.1.1", now=now + 3) > 0
    assert t.retry_after("a@b.c", "1.1.1.1", now=now + 100) == 0  # lock expires
    assert t.retry_after("other@b.c", "2.2.2.2", now=now + 3) == 0
    t.failure("a@b.c", "1.1.1.1", limit=3, lockout=60, now=now + 200)
    t.success("a@b.c", "1.1.1.1")
    assert t.failure("a@b.c", "1.1.1.1", limit=3, lockout=60, now=now + 201) == 2


def test_remember_me_sets_a_secure_httponly_cookie_and_restores_the_session(api_client: TestClient):
    email, pw = _register(api_client)
    api_client.cookies.clear()
    r = _login(api_client, email, pw, remember_me=True)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "saia_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "max-age=" in cookie
    assert "path=/api/v1/auth" in cookie
    assert "password" not in r.text.lower()
    # the cookie alone restores a bearer session
    restored = api_client.post("/api/v1/auth/session")
    assert restored.status_code == 200 and restored.json()["user"]["email"] == email
    me = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {restored.json()['access_token']}"})
    assert me.status_code == 200
    api_client.post("/api/v1/auth/logout")
    api_client.cookies.clear()
    assert api_client.post("/api/v1/auth/session").status_code == 401


def test_without_remember_me_the_cookie_is_a_browser_session_cookie(api_client: TestClient):
    email, pw = _register(api_client)
    api_client.cookies.clear()
    r = _login(api_client, email, pw)
    cookie = r.headers["set-cookie"].lower()
    assert "saia_session=" in cookie and "httponly" in cookie and "max-age" not in cookie
    secure = api_client.post("/api/v1/auth/login", json={"email": email, "password": pw, "remember_me": True},
                             headers={"X-Forwarded-Proto": "https"})
    assert "secure" in secure.headers["set-cookie"].lower()


def test_remember_me_token_lives_longer(api_client: TestClient):
    from app.application.token_service import decode_access_token

    email, pw = _register(api_client)
    secret = "dev-only-auth-secret-change-me"
    short = _login(api_client, email, pw).json()["access_token"]
    long_ = _login(api_client, email, pw, remember_me=True).json()["access_token"]
    s = get_settings()
    assert decode_access_token(long_, secret=secret)["exp"] - time.time() > s.auth_token_expiry_hours * 3600 * 2
    assert decode_access_token(short, secret=secret)["exp"] - time.time() <= s.auth_token_expiry_hours * 3600 + 5


def _google_env(monkeypatch, redirect: str | None = None):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "s3cret")
    if redirect:
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", redirect)
    else:
        monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    get_settings.cache_clear()


def test_google_button_needs_both_id_and_secret(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    assert api_client.get("/api/v1/auth/google/config").json() == {"enabled": False}
    assert api_client.get("/api/v1/auth/google/start", follow_redirects=False).status_code == 401
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    get_settings.cache_clear()
    try:
        assert api_client.get("/api/v1/auth/google/config").json() == {"enabled": False}  # id alone is not enough
    finally:
        get_settings.cache_clear()


def test_google_flow_uses_the_registered_redirect_uri_and_minimal_scopes(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from urllib.parse import parse_qs, urlparse

    _google_env(monkeypatch)  # no GOOGLE_REDIRECT_URI -> production default
    try:
        for base in ("/api/v1/auth/google", "/api/auth/google"):
            assert api_client.get(f"{base}/config").json() == {"enabled": True}
            r = api_client.get(f"{base}/start?next=/projects", follow_redirects=False)
            assert r.status_code == 302
            loc = urlparse(r.headers["location"])
            q = parse_qs(loc.query)
            assert loc.netloc == "accounts.google.com"
            assert q["redirect_uri"] == ["https://structuralai.ir/api/auth/google/callback"]
            assert q["scope"] == ["openid email profile"] and q["response_type"] == ["code"]
            assert q["client_id"] == ["cid.apps.googleusercontent.com"] and q["state"] and q["nonce"]
            assert "s3cret" not in r.headers["location"]
            ck = r.headers["set-cookie"].lower()
            assert "httponly" in ck and "samesite=lax" in ck and "secure" in ck and "path=/api" in ck
        # a cancelled / failed Google round trip lands on /login with a readable error, never a stack trace
        cb = api_client.get("/api/auth/google/callback?error=access_denied", follow_redirects=False)
        assert cb.status_code == 302 and cb.headers["location"].startswith("https://structuralai.ir/login#google_error=")
        # forged state is rejected
        bad = api_client.get("/api/auth/google/callback?code=x&state=forged.state", follow_redirects=False)
        assert "google_error=" in bad.headers["location"]
    finally:
        get_settings.cache_clear()


def test_google_callback_verifies_token_and_links_by_verified_email(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from urllib.parse import parse_qs, urlparse

    from app.application import google_oauth as g

    email, _pw = _register(api_client)
    _google_env(monkeypatch)
    try:
        start = api_client.get("/api/auth/google/start", follow_redirects=False)
        q = parse_qs(urlparse(start.headers["location"]).query)
        state, nonce = q["state"][0], q["nonce"][0]

        def fake_exchange(settings, code, n):
            assert code == "good-code" and n == nonce
            return {"email": email.upper(), "name": "Linked User", "email_verified": "true"}

        monkeypatch.setattr(g, "exchange_code", fake_exchange)
        no_cookie = api_client.get(f"/api/auth/google/callback?code=good-code&state={state}", follow_redirects=False)
        assert "google_error=" in no_cookie.headers["location"]  # state must match the browser's nonce cookie (CSRF)
        # (the cookie is Secure, so the plain-http test client would not echo it back; send it explicitly)
        ok = api_client.get(
            f"/api/auth/google/callback?code=good-code&state={state}",
            headers={"cookie": f"sa_google_nonce={nonce}"},
            follow_redirects=False,
        )
        assert "google_token=" in ok.headers["location"] and "google_error" not in ok.headers["location"]
        token = parse_qs(urlparse(ok.headers["location"]).fragment)["google_token"][0]
        me = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["email"] == email  # linked to the existing account, no duplicate
    finally:
        get_settings.cache_clear()


def test_google_claim_validation():
    from app.application.exceptions import AuthenticationError
    from app.application.google_oauth import validate_claims
    from app.infrastructure.config import Settings

    s = Settings(google_client_id="cid", google_client_secret="x")
    good = {"aud": "cid", "iss": "https://accounts.google.com", "exp": time.time() + 60, "nonce": "n", "email": "a@b.co", "email_verified": "true"}
    assert validate_claims(s, good, "n")["email"] == "a@b.co"
    for patch in ({"aud": "other"}, {"iss": "evil.com"}, {"exp": 1}, {"nonce": "zzz"}, {"email_verified": "false"}):
        with pytest.raises(AuthenticationError):
            validate_claims(s, {**good, **patch}, "n")


def test_google_is_not_offered_on_bare_ip_access(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "s3cret")
    get_settings.cache_clear()
    try:
        assert api_client.get("/api/v1/auth/google/config", headers={"Host": "structuralai.ir"}).json() == {"enabled": True}
        assert api_client.get("/api/auth/google/config", headers={"Host": "194.5.207.71"}).json() == {"enabled": False}
        assert api_client.get("/api/v1/auth/google/start", headers={"Host": "194.5.207.71"}, follow_redirects=False).status_code == 401
        assert api_client.get("/api/v1/auth/google/start", headers={"Host": "structuralai.ir"}, follow_redirects=False).status_code == 302
    finally:
        get_settings.cache_clear()


def test_google_start_from_www_restarts_on_the_callback_host(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "s3cret")
    get_settings.cache_clear()
    try:
        r = api_client.get("/api/v1/auth/google/start?next=%2Fprojects", headers={"Host": "www.structuralai.ir"}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "https://structuralai.ir/api/v1/auth/google/start?next=%2Fprojects"
        assert "set-cookie" not in r.headers  # no nonce cookie on the wrong host
        ok = api_client.get("/api/v1/auth/google/start", headers={"Host": "structuralai.ir"}, follow_redirects=False)
        assert ok.headers["location"].startswith("https://accounts.google.com/") and "sa_google_nonce" in ok.headers["set-cookie"]
    finally:
        get_settings.cache_clear()
