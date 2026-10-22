from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT = Path(__file__).with_name("plans.json")


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    path = Path(os.environ.get("BILLING_PLANS_FILE") or _DEFAULT)
    return json.loads(path.read_text(encoding="utf-8"))


def get_plan(plan_id: str) -> dict[str, Any]:
    for p in load_config()["plans"]:
        if p["id"] == plan_id:
            return p
    raise KeyError(plan_id)


def get_duration(duration_id: str) -> dict[str, Any]:
    for d in load_config()["durations"]:
        if d["id"] == duration_id:
            return d
    raise KeyError(duration_id)


def quote(plan_id: str, duration_id: str) -> dict[str, Any]:
    p, d = get_plan(plan_id), get_duration(duration_id)
    f = d["months"] * (100 - d["discount_pct"]) / 100
    toman = int(round(p["price_toman"] * f / 1000) * 1000)
    usdt = round(p["price_usdt"] * f, 2)
    return {"plan_id": p["id"], "duration_id": d["id"], "months": d["months"], "discount_pct": d["discount_pct"],
            "amount_toman": toman, "amount_rial": toman * 10, "amount_usdt": usdt,
            "list_toman": p["price_toman"] * d["months"], "list_usdt": p["price_usdt"] * d["months"]}


def catalog() -> dict[str, Any]:
    cfg = load_config()
    plans = []
    for p in cfg["plans"]:
        plans.append({**p, "quotes": {d["id"]: quote(p["id"], d["id"]) for d in cfg["durations"]}})
    return {"plans": plans, "durations": cfg["durations"], "currency_note": cfg.get("currency_note", "")}
