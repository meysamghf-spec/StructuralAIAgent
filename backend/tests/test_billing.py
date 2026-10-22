from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from app.application.billing import plans, service, store


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_root", lambda: (tmp_path / "accounts").mkdir(exist_ok=True) or tmp_path)
    monkeypatch.setenv("BILLING_ENFORCEMENT", "1")
    for k in ("CRYPTO_TRON_ADDRESS", "CRYPTO_EVM_ADDRESS", "CRYPTO_TON_ADDRESS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CRYPTO_RATES_JSON", '{"BTC": 65000}')
    for k in ("BTCPAY_SERVER_URL", "BTCPAY_API_KEY", "BTCPAY_STORE_ID", "BILLING_COMPLIMENTARY_ACCOUNTS"):
        monkeypatch.delenv(k, raising=False)


def test_quote_discounts():
    q1, q12 = plans.quote("pro", "1m"), plans.quote("pro", "12m")
    assert q1["amount_toman"] == 1_490_000 and q1["amount_rial"] == 14_900_000
    assert q12["amount_toman"] < 12 * 1_490_000 and q12["discount_pct"] == 25


def _buy(acc, plan="pro", dur="1m", asset="usdt-trc20", status="OK"):
    inv = service.create_checkout(acc, plan, dur, asset)["invoice"]
    assert inv["mock"] and inv["pay_address"] and "<svg" in inv["qr_svg"] and inv["expires_at"]
    return service.mock_confirm(acc, inv["id"], ok=status == "OK")


def test_assets_and_quotes():
    from app.application.billing import crypto
    ids = {a["id"] for a in crypto.asset_catalog()}
    assert {"usdt-trc20", "usdt-bep20", "usdt-erc20", "usdt-polygon", "usdc-erc20", "usdc-bep20", "usdc-polygon",
            "btc-onchain", "btc-lightning", "eth", "trx", "bnb"} <= ids
    a = crypto.BY_ID["usdt-trc20"]
    amt = float(crypto.quote_crypto(a, 15)["amount_crypto"])
    assert 15 < amt < 16
    uri = crypto.payment_uri(crypto.BY_ID["usdt-bep20"], "0xabc", "15.123")
    assert uri.startswith("ethereum:0x55d3") and "@56/" in uri and "uint256=15123000000000000000" in uri


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

    assert _buy(acc, status="NOK")["status"] == "cancelled"
    assert service.current_plan(acc)["id"] == "free"
    inv = _buy(acc)
    assert inv["status"] == "paid" and inv["mock"]
    assert service.current_plan(acc)["id"] == "pro"
    service.check_frame_size(acc, {"storeys": 8, "bays_x": 3})
    service.require_feature(acc, "exports", "e2k")
    exp1 = store.load(acc)["subscription"]["expires_at"]
    _buy(acc, asset="btc-onchain", dur="3m")
    s = service.account_summary(acc)
    assert s["subscription"]["expires_at"] > exp1 and s["history"][0]["action"] == "renewed"
    assert len(s["invoices"]) == 3


def test_free_not_purchasable():
    with pytest.raises(service.ApplicationError):
        service.create_checkout("a2", "free", "1m", "usdt-trc20")
