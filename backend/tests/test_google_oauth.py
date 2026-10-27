"""Unit tests for the Google OIDC helpers (no network)."""

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import SecretStr

from app.application import google_oauth as g
from app.infrastructure.config import Settings


def _settings(**kw):
    base = dict(
        google_oauth_enabled=True,
        google_client_id="cid",
        google_client_secret=SecretStr("sec"),
        google_oauth_redirect_uri="https://ex.ir/api/auth/google/callback",
    )
    base.update(kw)
    return Settings(**base)


def _jwt(claims: dict) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.sig"


def _claims(**over):
    c = {"aud": "cid", "iss": "https://accounts.google.com", "exp": int(time.time()) + 60, "nonce": "n",
         "sub": "123", "email": "a@b.ir", "email_verified": True}
    c.update(over)
    return c


def test_disabled_by_default_and_needs_flag_id_and_secret():
    assert not g.google_enabled(Settings(google_client_id=None, google_client_secret=None))
    assert not g.google_enabled(_settings(google_oauth_enabled=False))  # credentials alone are not enough
    assert not g.google_enabled(_settings(google_client_id=None))
    assert not g.google_enabled(_settings(google_client_secret=None))
    assert g.google_enabled(_settings())
    assert g.post_login_url(_settings()) == "https://ex.ir/login"


def test_redirect_uri_env_names_and_default():
    assert Settings().google_callback_url == "https://structuralai.ir/api/auth/google/callback"
    assert Settings(google_redirect_uri="https://old/cb").google_callback_url == "https://old/cb"
    assert Settings(google_redirect_uri="https://old/cb", google_oauth_redirect_uri="https://new/cb").google_callback_url == "https://new/cb"


def test_state_roundtrip_tamper_expiry_and_cookie_binding():
    st = g.make_state("k", "n1", "/projects", remember=True)
    data = g.read_state("k", st, "n1")
    assert data["p"] == "/projects" and data["r"] == 1
    for bad_state, cookie, key in ((st, "other", "k"), (st, None, "k"), (st, "n1", "k2"), ("junk", "n1", "k"), ("a.b", "n1", "k"), (st[:-3] + "xxx", "n1", "k")):
        with pytest.raises(g.GoogleSignInError) as ei:
            g.read_state(key, bad_state, cookie)
        assert ei.value.code == "state"
    payload = base64.urlsafe_b64encode(json.dumps({"n": "n1", "x": int(time.time()) - 5, "p": "/"}).encode()).decode().rstrip("=")
    expired = f"{payload}.{g._sign('k', payload)}"
    with pytest.raises(g.GoogleSignInError):
        g.read_state("k", expired, "n1")


def test_pkce_challenge_matches_rfc7636_and_url_params():
    # RFC 7636 appendix B vector
    assert g.code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    v = g.code_verifier("secret", "nonce")
    assert 43 <= len(v) <= 128 and v == g.code_verifier("secret", "nonce") and v != g.code_verifier("secret", "other")
    q = parse_qs(urlparse(g.authorization_url(_settings(), "st", "no", v)).query)
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] == [g.code_challenge(v)]
    assert q["scope"] == ["openid email profile"] and q["response_type"] == ["code"] and "client_secret" not in q
    assert q["redirect_uri"] == ["https://ex.ir/api/auth/google/callback"] and q["nonce"] == ["no"] and q["state"] == ["st"]


def test_claim_validation():
    s = _settings()
    assert g.validate_claims(s, _claims(), "n")["email"] == "a@b.ir"
    assert g.validate_claims(s, _claims(email_verified="true"), "n")  # string form
    assert g.validate_claims(s, _claims(iss="accounts.google.com"), "n")
    assert g.validate_claims(s, _claims(aud=["cid", "other"], azp="cid"), "n")
    for bad in ({"aud": "x"}, {"aud": ["cid", "o"], "azp": "o"}, {"iss": "evil"}, {"exp": 1}, {"exp": "zz"}, {"nonce": "z"}, {"nonce": None}, {"sub": ""}):
        with pytest.raises(g.GoogleSignInError) as ei:
            g.validate_claims(s, _claims(**bad), "n")
        assert ei.value.code == "token_invalid"
    for bad in ({"email_verified": False}, {"email_verified": "false"}, {"email_verified": None}, {"email": ""}):
        with pytest.raises(g.GoogleSignInError) as ei:
            g.validate_claims(s, _claims(**bad), "n")
        assert ei.value.code == "email_unverified"


def test_safe_next():
    assert g.safe_next("/projects?a=1") == "/projects?a=1"
    for bad in (None, "", "https://evil.com", "//evil.com", "/\\evil.com", "evil", "/a\nb"):
        assert g.safe_next(bad) == "/"


def _patch_client(monkeypatch, handler, seen=None):
    real = httpx.Client

    def factory(settings):
        kw = {"transport": httpx.MockTransport(handler), "timeout": 5}
        if seen is not None:
            seen["proxy"] = settings.google_oauth_proxy.get_secret_value() if settings.google_oauth_proxy else None
        return real(**kw)

    monkeypatch.setattr(g, "_http_client", factory)


def test_exchange_code_sends_pkce_verifier_and_validates(monkeypatch):
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["form"] = parse_qs(req.content.decode())
        return httpx.Response(200, json={"id_token": _jwt(_claims()), "access_token": "ignored"})

    _patch_client(monkeypatch, handler)
    claims = g.exchange_code(_settings(), "the-code", "n", "ver1fier")
    assert claims["email"] == "a@b.ir" and seen["url"] == g.TOKEN_URL
    assert seen["form"]["code_verifier"] == ["ver1fier"] and seen["form"]["grant_type"] == ["authorization_code"]
    assert seen["form"]["redirect_uri"] == ["https://ex.ir/api/auth/google/callback"] and seen["form"]["code"] == ["the-code"]


@pytest.mark.parametrize("resp,code", [
    (httpx.Response(400, json={"error": "invalid_grant"}), "token_exchange"),
    (httpx.Response(200, json={}), "token_exchange"),
    (httpx.Response(200, text="not json"), "token_exchange"),
    (httpx.Response(200, json={"id_token": "garbage"}), "token_invalid"),
    (httpx.Response(200, json={"id_token": _jwt(_claims(email_verified=False))}), "email_unverified"),
    (httpx.Response(200, json={"id_token": _jwt(_claims(nonce="other"))}), "token_invalid"),
])
def test_exchange_code_failures(monkeypatch, resp, code):
    _patch_client(monkeypatch, lambda req: resp)
    with pytest.raises(g.GoogleSignInError) as ei:
        g.exchange_code(_settings(), "c", "n", "v")
    assert ei.value.code == code


def test_exchange_code_unreachable_is_reported_not_crashed(monkeypatch):
    def boom(req):
        raise httpx.ConnectTimeout("blocked")

    _patch_client(monkeypatch, boom)
    with pytest.raises(g.GoogleSignInError) as ei:
        g.exchange_code(_settings(), "c", "n", "v")
    assert ei.value.code == "unreachable"


def test_proxy_setting_is_passed_to_the_http_client(monkeypatch):
    captured = {}
    real = httpx.Client

    def spy(**kw):
        captured.update(kw)
        return real(**{k: v for k, v in kw.items() if k != "proxy"})

    monkeypatch.setattr(httpx, "Client", spy)
    g._http_client(_settings(google_oauth_proxy=SecretStr("http://user:pw@proxy.example:3128"))).close()
    assert captured["proxy"] == "http://user:pw@proxy.example:3128"
    captured.clear()
    g._http_client(_settings()).close()
    assert captured["proxy"] is None
