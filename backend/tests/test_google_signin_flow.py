"""Sign in with Google, end to end through the API with Google's endpoints mocked (no network)."""

from __future__ import annotations

import base64
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.application import google_oauth as g
from app.application.login_throttle import login_throttle
from app.api.routes.auth import SESSION_COOKIE
from app.application.token_service import decode_access_token
from app.infrastructure.config import get_settings

CID = "cid.apps.googleusercontent.com"
CB = "https://structuralai.ir/api/auth/google/callback"


@pytest.fixture(autouse=True)
def _reset():
    login_throttle.reset()
    yield
    get_settings.cache_clear()


def _env(monkeypatch, *, enabled=True, redirect=None):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "s3cret-value")
    for k in ("GOOGLE_OAUTH_ENABLED", "GOOGLE_REDIRECT_URI", "GOOGLE_OAUTH_REDIRECT_URI"):
        monkeypatch.delenv(k, raising=False)
    if enabled:
        monkeypatch.setenv("GOOGLE_OAUTH_ENABLED", "true")
    if redirect:
        monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", redirect)
    get_settings.cache_clear()


def _jwt(claims: dict) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.sig"


def _mock_google(monkeypatch, *, email, verified=True, name="G User", status=200, nonce_override=None, record=None):
    """Mock oauth2.googleapis.com/token: echoes the nonce we put in the authorization request."""
    real = httpx.Client

    def handler(req: httpx.Request):
        form = parse_qs(req.content.decode())
        if record is not None:
            record.append(form)
        if status != 200:
            return httpx.Response(status, json={"error": "invalid_grant"})
        claims = {"aud": CID, "iss": "https://accounts.google.com", "exp": int(time.time()) + 300, "sub": "sub-1",
                  "nonce": nonce_override or _mock_google.nonce, "email": email, "email_verified": verified, "name": name}
        return httpx.Response(200, json={"id_token": _jwt(claims)})

    monkeypatch.setattr(g, "_http_client", lambda settings: real(transport=httpx.MockTransport(handler), timeout=5))


def _start(client: TestClient, query="", host="structuralai.ir"):
    r = client.get(f"/api/auth/google/start{query}", headers={"Host": host}, follow_redirects=False)
    assert r.status_code == 302, r.text
    q = parse_qs(urlparse(r.headers["location"]).query)
    _mock_google.nonce = q["nonce"][0]
    return r, q


def _callback(client, q, code="good", state=None, cookie=True, extra=""):
    headers = {"Host": "structuralai.ir"}
    if cookie:
        headers["cookie"] = f"sa_google_nonce={q['nonce'][0]}"  # the cookie is Secure; the plain-http test client won't echo it
    return client.get(f"/api/auth/google/callback?code={code}&state={state or q['state'][0]}{extra}", headers=headers, follow_redirects=False)


def _register(client) -> str:
    email = f"g-{uuid.uuid4().hex[:8]}@example.com"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": "secure-password"}).status_code == 201
    return email


def _error(resp) -> str:
    frag = parse_qs(urlparse(resp.headers["location"]).fragment)
    return frag.get("google_error", [""])[0]


def test_default_is_disabled_even_with_credentials(api_client: TestClient, monkeypatch):
    _env(monkeypatch, enabled=False)
    for base in ("/api/v1/auth/google", "/api/auth/google"):
        assert api_client.get(f"{base}/config").json() == {"enabled": False, "reason": None}
    r = api_client.get("/api/auth/google/start", follow_redirects=False)
    assert r.status_code == 302 and "google_error=not_configured" in r.headers["location"] and "accounts.google.com" not in r.headers["location"]
    cb = api_client.get("/api/auth/google/callback?code=x&state=y", follow_redirects=False)
    assert "google_error=not_configured" in cb.headers["location"]


def test_enabled_start_redirects_with_pkce_state_nonce_and_secure_cookie(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    assert api_client.get("/api/v1/auth/google/config", headers={"Host": "structuralai.ir"}).json() == {"enabled": True, "reason": None}
    for base in ("/api/v1/auth/google", "/api/auth/google"):
        r = api_client.get(f"{base}/start?next=/projects&remember=true", headers={"Host": "structuralai.ir"}, follow_redirects=False)
        loc = urlparse(r.headers["location"])
        q = parse_qs(loc.query)
        assert loc.netloc == "accounts.google.com" and q["redirect_uri"] == [CB] and q["client_id"] == [CID]
        assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] and q["state"] and q["nonce"]
        assert q["scope"] == ["openid email profile"] and "s3cret-value" not in r.headers["location"]
        ck = r.headers["set-cookie"].lower()
        assert "sa_google_nonce=" in ck and "httponly" in ck and "samesite=lax" in ck and "secure" in ck and "path=/api" in ck
        assert g.read_state("dev-only-auth-secret-change-me", q["state"][0], q["nonce"][0])["r"] == 1


def test_open_redirect_in_next_is_neutralised(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    _r, q = _start(api_client, "?next=//evil.example/x")
    assert g.read_state("dev-only-auth-secret-change-me", q["state"][0], q["nonce"][0])["p"] == "/"


def test_state_mismatch_and_missing_cookie_are_rejected(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    email = _register(api_client)
    _mock_google(monkeypatch, email=email)
    _r, q = _start(api_client)
    assert _error(_callback(api_client, q, cookie=False)) == "state"  # other browser / CSRF: no nonce cookie
    r = api_client.get(f"/api/auth/google/callback?code=x&state={q['state'][0]}", headers={"cookie": "sa_google_nonce=somebody-elses"}, follow_redirects=False)
    assert _error(r) == "state"
    assert _error(_callback(api_client, q, state="forged.state")) == "state"
    bad = q["state"][0][:-2] + "AA"
    assert _error(_callback(api_client, q, state=bad)) == "state"
    ok = _callback(api_client, q)
    assert "google=ok" in ok.headers["location"]


def test_unverified_email_is_refused_and_creates_nothing(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    email = f"unv-{uuid.uuid4().hex[:6]}@example.com"
    _mock_google(monkeypatch, email=email, verified=False)
    _r, q = _start(api_client)
    resp = _callback(api_client, q)
    assert _error(resp) == "email_unverified" and "set-cookie" in resp.headers
    assert SESSION_COOKIE not in resp.headers["set-cookie"] or f'{SESSION_COOKIE}=""' in resp.headers["set-cookie"]
    # the email was not registered
    r = api_client.post("/api/v1/auth/login", json={"email": email, "password": "whatever-pass"})
    assert r.json()["error"]["code"] == "EMAIL_NOT_REGISTERED"


def test_existing_account_is_linked_by_verified_email_and_gets_the_same_session_cookie(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    email = _register(api_client)
    me_before = api_client.post("/api/v1/auth/login", json={"email": email, "password": "secure-password"}).json()["user"]
    api_client.cookies.clear()
    _mock_google(monkeypatch, email=email.upper())  # Google may return different case
    _r, q = _start(api_client, "?next=/projects")
    resp = _callback(api_client, q)
    frag = parse_qs(urlparse(resp.headers["location"]).fragment)
    assert frag["google"] == ["ok"] and frag["r"] == ["0"] and frag["next"] == ["/projects"] and "token" not in resp.headers["location"]
    set_cookie = resp.headers.get_list("set-cookie")
    sess = next(c for c in set_cookie if c.startswith(f"{SESSION_COOKIE}="))
    low = sess.lower()
    assert "httponly" in low and "samesite=lax" in low and "path=/api/v1/auth" in low and "max-age" not in low  # browser-session cookie
    assert any(c.startswith("sa_google_nonce=") and ("max-age=0" in c.lower() or "expires" in c.lower()) for c in set_cookie)  # nonce cleared
    # the browser then trades the cookie for a bearer token exactly like a "remember me" restore
    token_cookie = sess.split(";")[0].split("=", 1)[1]
    r = api_client.post("/api/v1/auth/session", headers={"cookie": f"{SESSION_COOKIE}={token_cookie}"})
    assert r.status_code == 200 and r.json()["user"]["id"] == me_before["id"] and r.json()["user"]["email"] == email  # linked, no duplicate
    bearer = r.json()["access_token"]
    assert api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bearer}"}).json()["id"] == me_before["id"]


def test_new_account_is_created_for_unknown_verified_email(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    email = f"new-{uuid.uuid4().hex[:8]}@example.com"
    _mock_google(monkeypatch, email=email, name="New Person")
    _r, q = _start(api_client)
    resp = _callback(api_client, q)
    assert "google=ok" in resp.headers["location"]
    sess = next(c for c in resp.headers.get_list("set-cookie") if c.startswith(f"{SESSION_COOKIE}="))
    r = api_client.post("/api/v1/auth/session", headers={"cookie": f"{SESSION_COOKIE}={sess.split(';')[0].split('=', 1)[1]}"})
    assert r.json()["user"]["email"] == email and r.json()["user"]["display_name"] == "New Person"
    # a second Google login does not create a duplicate
    _r, q = _start(api_client)
    _callback(api_client, q)
    r2 = api_client.post("/api/v1/auth/session", headers={"cookie": f"{SESSION_COOKIE}={sess.split(';')[0].split('=', 1)[1]}"})
    assert r2.json()["user"]["id"] == r.json()["user"]["id"]


def test_remember_me_extends_cookie_and_token_lifetime(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    email = _register(api_client)
    _mock_google(monkeypatch, email=email)
    _r, q = _start(api_client, "?remember=true")
    resp = _callback(api_client, q)
    assert "r=1" in resp.headers["location"]
    sess = next(c for c in resp.headers.get_list("set-cookie") if c.startswith(f"{SESSION_COOKIE}="))
    s = get_settings()
    assert f"max-age={s.auth_remember_expiry_hours * 3600}" in sess.lower()
    token = sess.split(";")[0].split("=", 1)[1]
    assert decode_access_token(token, secret="dev-only-auth-secret-change-me")["exp"] - time.time() > s.auth_token_expiry_hours * 3600 * 2


def test_pkce_verifier_and_secret_go_to_google_only_server_side(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    email = _register(api_client)
    rec: list = []
    _mock_google(monkeypatch, email=email, record=rec)
    _r, q = _start(api_client)
    resp = _callback(api_client, q)
    form = rec[0]
    assert g.code_challenge(form["code_verifier"][0]) == q["code_challenge"][0]
    assert form["client_secret"] == ["s3cret-value"] and form["redirect_uri"] == [CB]
    assert "s3cret-value" not in resp.headers["location"] and form["code_verifier"][0] not in resp.headers["location"]


def test_google_failures_land_on_login_with_a_code_never_a_stack_trace(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    email = _register(api_client)
    _r, q = _start(api_client)
    assert _error(api_client.get("/api/auth/google/callback?error=access_denied", headers={"Host": "structuralai.ir"}, follow_redirects=False)) == "cancelled"
    assert _error(api_client.get("/api/auth/google/callback?error=server_error", headers={"Host": "structuralai.ir"}, follow_redirects=False)) == "failed"
    _mock_google(monkeypatch, email=email, status=400)
    assert _error(_callback(api_client, q)) == "token_exchange"
    _mock_google(monkeypatch, email=email, nonce_override="not-ours")
    assert _error(_callback(api_client, q)) == "token_invalid"

    def boom(req):
        raise httpx.ConnectTimeout("google unreachable")

    real = httpx.Client
    monkeypatch.setattr(g, "_http_client", lambda s: real(transport=httpx.MockTransport(boom)))
    resp = _callback(api_client, q)
    assert _error(resp) == "unreachable" and resp.headers["location"].startswith("https://structuralai.ir/login#")


def test_disabled_account_cannot_sign_in_with_google(api_client: TestClient, monkeypatch):
    from app.application.exceptions import AccountDisabledError
    from app.application.auth_service import AuthService

    _env(monkeypatch)
    email = _register(api_client)
    _mock_google(monkeypatch, email=email)

    def disabled(self, **kw):
        raise AccountDisabledError()

    monkeypatch.setattr(AuthService, "login_with_google", disabled)
    _r, q = _start(api_client)
    assert _error(_callback(api_client, q)) == "account_disabled"


def test_not_offered_on_bare_ip_and_www_restarts_on_callback_host(api_client: TestClient, monkeypatch):
    _env(monkeypatch)
    assert api_client.get("/api/auth/google/config", headers={"Host": "194.5.207.71"}).json() == {"enabled": False, "reason": "ip_host"}
    r = api_client.get("/api/auth/google/start", headers={"Host": "194.5.207.71"}, follow_redirects=False)
    assert "google_error=not_configured" in r.headers["location"] and "accounts.google.com" not in r.headers["location"]
    w = api_client.get("/api/v1/auth/google/start?next=%2Fprojects&remember=true", headers={"Host": "www.structuralai.ir"}, follow_redirects=False)
    assert w.headers["location"] == "https://structuralai.ir/api/v1/auth/google/start?next=%2Fprojects&remember=true"
    assert "set-cookie" not in w.headers


def test_custom_redirect_uri_env_is_used(api_client: TestClient, monkeypatch):
    _env(monkeypatch, redirect="https://staging.example/api/auth/google/callback")
    r = api_client.get("/api/auth/google/start", headers={"Host": "staging.example"}, follow_redirects=False)
    assert parse_qs(urlparse(r.headers["location"]).query)["redirect_uri"] == ["https://staging.example/api/auth/google/callback"]


def test_email_login_still_works_and_secret_is_not_logged(api_client: TestClient, monkeypatch, caplog):
    _env(monkeypatch)
    email = _register(api_client)
    assert api_client.post("/api/v1/auth/login", json={"email": email, "password": "secure-password"}).status_code == 200
    _mock_google(monkeypatch, email=email, status=400)
    _r, q = _start(api_client)
    with caplog.at_level("DEBUG"):
        _callback(api_client, q)
    assert "s3cret-value" not in caplog.text
