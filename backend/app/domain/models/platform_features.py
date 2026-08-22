"""Platform feature identifiers and upgrade product mapping."""

from __future__ import annotations

from enum import StrEnum


class PlatformFeature(StrEnum):
    MULTI_MEMBER_OPTIMIZATION = "multi_member_optimization"
    CSI_DEEP_EXTRACTION = "csi_deep_extraction"
    CAD_PLAN_GENERATION = "cad_plan_generation"


FEATURE_UPGRADE_PRODUCT: dict[PlatformFeature, str | None] = {
    PlatformFeature.MULTI_MEMBER_OPTIMIZATION: "pro-workspace",
    PlatformFeature.CSI_DEEP_EXTRACTION: "solver-plus",
    PlatformFeature.CAD_PLAN_GENERATION: "solver-plus",
}
