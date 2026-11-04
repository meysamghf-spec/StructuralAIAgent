"""TEMPORARY test plan for verifying a real on-chain payment end to end.

Hidden 1 USDT plan that is visible and purchasable ONLY by account ids listed in
CRYPTO_TEST_PLAN_USER_IDS (comma separated). Empty/unset = feature fully off.
Paying it activates Pro-equivalent limits for CRYPTO_TEST_PLAN_DAYS (default 1) day(s).
To remove: unset the env var (or delete this module and its few call sites marked "TEST PLAN").
"""
from __future__ import annotations

import os
from typing import Any

from .plans import get_plan

TEST_PLAN_ID = "test_pro_1d"
GRANTS_PLAN_ID = "pro"


def allowed_ids() -> set[str]:
    return {x.strip().lower() for x in (os.environ.get("CRYPTO_TEST_PLAN_USER_IDS") or "").split(",") if x.strip()}


def is_allowed(account_id: str) -> bool:
    ids = allowed_ids()
    return bool(ids) and account_id.lower() in ids


def price_usdt() -> float:
    try:
        return float(os.environ.get("CRYPTO_TEST_PLAN_USDT") or 1)
    except ValueError:
        return 1.0


def days() -> int:
    try:
        return max(1, int(os.environ.get("CRYPTO_TEST_PLAN_DAYS") or 1))
    except ValueError:
        return 1


def quote() -> dict[str, Any]:
    usdt = round(price_usdt(), 2)
    return {"plan_id": TEST_PLAN_ID, "duration_id": "1m", "months": 0, "days": days(), "discount_pct": 0,
            "amount_toman": 0, "amount_rial": 0, "amount_usdt": usdt, "list_toman": 0, "list_usdt": usdt}


def plan() -> dict[str, Any]:
    pro = get_plan(GRANTS_PLAN_ID)
    return {**pro, "id": TEST_PLAN_ID, "name": f"TEST – Pro {days()} day", "name_fa": f"آزمایشی – حرفه‌ای {days()} روزه",
            "tagline": "Test plan for a real on-chain payment. Visible only to your account.",
            "price_toman": 0, "price_usdt": price_usdt(), "purchasable": True, "highlight": False, "test": True,
            "grants_plan_id": GRANTS_PLAN_ID, "quotes": {"1m": quote()}}
