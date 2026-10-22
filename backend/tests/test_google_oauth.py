import time

import pytest
from pydantic import SecretStr

from app.application import google_oauth as g
from app.application.exceptions import AuthenticationError
from app.infrastructure.config import Settings


def _settings(**kw):
    base = dict(google_client_id="cid", google_client_secret=SecretStr("sec"), google_redirect_uri="https://ex.ir/api/v1/auth/google/callback")
    base.update(kw)
    return Settings(**base)


def test_disabled_without_env():
    assert not g.google_enabled(Settings(google_client_id=None, google_client_secret=None, google_redirect_uri=None))
    assert g.google_enabled(_settings())
    assert g.post_login_url(_settings()) == "https://ex.ir/login"


def test_state_roundtrip_and_tamper():
    st = g.make_state("k", "n1", "/projects")
    assert g.read_state("k", st, "n1")["p"] == "/projects"
    with pytest.raises(AuthenticationError):
        g.read_state("k", st, "other")
    with pytest.raises(AuthenticationError):
        g.read_state("k2", st, "n1")


def test_claims_validation():
    s = _settings()
    ok = {"aud": "cid", "iss": "https://accounts.google.com", "exp": str(int(time.time()) + 60), "nonce": "n", "email": "a@b.ir", "email_verified": "true"}
    assert g.validate_claims(s, ok, "n")["email"] == "a@b.ir"
    for bad in ({"aud": "x"}, {"email_verified": "false"}, {"nonce": "z"}, {"iss": "evil"}):
        with pytest.raises(AuthenticationError):
            g.validate_claims(s, {**ok, **bad}, "n")
