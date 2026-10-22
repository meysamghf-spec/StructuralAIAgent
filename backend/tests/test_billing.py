from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from app.application.billing import plans, service, store


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_root", lambda: (tmp_path / "accounts").mkdir(exist_ok=True) or tmp_path)
    monkeypatch.setenv("BILLING_ENFORCEMENT", "1")
    monkeypatch.setenv("BILLING_CARD_GATEWAY", "mock")
    for k in ("BTCPAY_SERVER_URL", "BTCPAY_API_KEY", "BTCPAY_STORE_ID", "BILLING_COMPLIMENTARY_ACCOUNTS"):
        monkeypatch.delenv(k, raising=False)


def test_quote_discounts():
    q1, q12 = plans.quote("pro", "1m"), plans.quote("pro", "12m")
    assert q1["amount_toman"] == 1_490_000 and q1["amount_rial"] == 14_900_000
    assert q12["amount_toman"] < 12 * 1_490_000 and q12["discount_pct"] == 25


def _buy(acc, plan="pro", dur="1m", method="card", status="OK"):
    out = service.create_checkout(acc, plan, dur, method, api_base="http://x", frontend_base="http://x")
    assert "/workspace/upgrades/mock-pay" in out["redirect_url"]
    q = parse_qs(urlparse(out["redirect_url"]).query)
    return service.complete(q["invoice"][0], {"Status": status}, frontend_base="http://x")[1]


def test_free_limits_then_upgrade_and_renewal():
    acc = "a1"
    assert service.current_plan(acc)["id"] == "free"
    with pytest.raises(service.QuotaExceededError) as e:
        service.check_frame_size(acc, {"storeys": 8, "bays_x": 3})
    assert e.value.status_code == 402 and e.value.details["upgrade_plan_id"] == "pro"
    with pytest.raises(service.QuotaExceededError):
        service.require_feature(acc, "exports", "e2k")
    with pytest.raises(service.QuotaExceededError):
        service.require_count(acc, "projects", 2)
    for _ in range(15):
        service.consume(acc, "analyses_per_month")
    with pytest.raises(service.QuotaExceededError):
        service.consume(acc, "analyses_per_month")

    assert _buy(acc, status="NOK")["status"] == "failed"
    assert service.current_plan(acc)["id"] == "free"
    inv = _buy(acc)
    assert inv["status"] == "paid" and inv["mock"]
    assert service.current_plan(acc)["id"] == "pro"
    service.check_frame_size(acc, {"storeys": 8, "bays_x": 3})
    service.require_feature(acc, "exports", "e2k")
    exp1 = store.load(acc)["subscription"]["expires_at"]
    _buy(acc, method="crypto", dur="3m")
    s = service.account_summary(acc)
    assert s["subscription"]["expires_at"] > exp1 and s["history"][0]["action"] == "renewed"
    assert len(s["invoices"]) == 3


def test_free_not_purchasable():
    with pytest.raises(service.ApplicationError):
        service.create_checkout("a2", "free", "1m", "card", api_base="x", frontend_base="x")
