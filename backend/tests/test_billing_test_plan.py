"""TEST PLAN: hidden 1 USDT plan, only for CRYPTO_TEST_PLAN_USER_IDS accounts; grants Pro for 1 day."""
from datetime import datetime

import pytest

from app.application.billing import service, store, test_plan
from app.application.billing.plans import catalog
from app.application.exceptions import ApplicationError
from tests.test_billing_bep20 import CONF, buy, chain, paid, scan, units  # noqa: F401  (chain = fixture)


def test_off_by_default(chain, monkeypatch):
    monkeypatch.delenv("CRYPTO_TEST_PLAN_USER_IDS", raising=False)
    assert service.account_summary("me")["test_plan"] is None
    with pytest.raises(ApplicationError):
        buy("me", test_plan.TEST_PLAN_ID)
    assert test_plan.TEST_PLAN_ID not in [p["id"] for p in catalog()["plans"]]


def test_only_allowlisted_account(chain, monkeypatch):
    monkeypatch.setenv("CRYPTO_TEST_PLAN_USER_IDS", "me, someone")
    assert service.account_summary("me")["test_plan"]["price_usdt"] == 1
    assert service.account_summary("other")["test_plan"] is None
    with pytest.raises(ApplicationError):
        buy("other", test_plan.TEST_PLAN_ID)


def test_real_payment_flow_grants_pro_one_day(chain, monkeypatch):
    monkeypatch.setenv("CRYPTO_TEST_PLAN_USER_IDS", "me")
    inv = buy("me", test_plan.TEST_PLAN_ID)
    assert 1 <= float(inv["amount_crypto"]) < 2 and inv["amount_usdt"] == 1 and not inv["mock"]
    chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(CONF + 1)
    scan()
    assert paid("me", inv["id"])["status"] == "paid"
    assert service.current_plan("me")["id"] == "pro"
    sub = store.load("me")["subscription"]
    hours = (datetime.fromisoformat(sub["expires_at"]) - service._now()).total_seconds() / 3600
    assert 23 < hours <= 24
