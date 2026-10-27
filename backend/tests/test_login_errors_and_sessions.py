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
