"""Helpers for deciding when paid platform features are required."""

from __future__ import annotations

from typing import Any

from app.domain.models.optimization import OptimizationMode


def optimization_requires_paid_entitlement(parameters: dict[str, Any]) -> bool:
    mode = parameters.get("optimization_mode")
    if mode == OptimizationMode.SHARED_SECTION.value:
        return True
    member_ids = parameters.get("member_ids")
    return isinstance(member_ids, list) and len(member_ids) > 1
