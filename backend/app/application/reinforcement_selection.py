"""Reusable bar-selection engine. Areas are millimetres squared, spacing millimetres."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.models.pem_structural import ReinforcementBarSet, StirrupLayout

BAR_DIAMETERS_MM = (10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 25.0, 28.0, 32.0)


def bar_area_mm2(diameter_mm: float) -> float:
    return math.pi * (diameter_mm / 2.0) ** 2


@dataclass(frozen=True)
class BarSelection:
    bars: ReinforcementBarSet
    required_mm2: float
    provided_mm2: float
    utilization: float


class ReinforcementSelectionEngine:
    def select_longitudinal(
        self,
        as_required_mm2: float,
        *,
        width_mm: float,
        depth_mm: float,
        cover_mm: float = 40.0,
        min_count: int = 2,
        max_count: int | None = None,
        diameters: tuple[float, ...] = BAR_DIAMETERS_MM,
        layer: str = "LONGITUDINAL",
    ) -> BarSelection:
        clear = max(width_mm - 2.0 * cover_mm, 40.0)
        max_by_spacing = max(min_count, int(clear / 50.0) + 1)
        cap = max_count or max_by_spacing
        best: ReinforcementBarSet | None = None
        for diameter in diameters:
            area = bar_area_mm2(diameter)
            count = min_count if as_required_mm2 <= 0 else max(min_count, int(math.ceil(as_required_mm2 / area)))
            count = min(count, cap)
            spacing = (clear - count * diameter) / max(count - 1, 1) if count > 1 else clear
            if spacing < 25.0 and count > min_count:
                continue
            candidate = ReinforcementBarSet(
                designation=f"{diameter:.0f}M",
                diameter_mm=diameter,
                count=count,
                area_each_mm2=round(area, 1),
                spacing_mm=round(max(spacing, 0.0), 1),
                layer=layer,
                metadata={"cover_mm": cover_mm},
            )
            if candidate.total_area_mm2 + 1e-6 >= as_required_mm2:
                if best is None or candidate.total_area_mm2 < best.total_area_mm2:
                    best = candidate
        if best is None:
            diameter = diameters[-1]
            best = ReinforcementBarSet(
                designation=f"{diameter:.0f}M",
                diameter_mm=diameter,
                count=cap,
                area_each_mm2=round(bar_area_mm2(diameter), 1),
                layer=layer,
            )
        provided = best.total_area_mm2
        util = as_required_mm2 / provided if provided > 0 else 0.0
        return BarSelection(bars=best, required_mm2=as_required_mm2, provided_mm2=provided, utilization=util)

    def select_stirrups(
        self,
        *,
        vs_needed_kn: float,
        width_mm: float,
        d_mm: float,
        fy_mpa: float,
        diameter_mm: float = 10.0,
        legs: int = 2,
    ) -> StirrupLayout:
        av = legs * bar_area_mm2(diameter_mm)
        if vs_needed_kn <= 0:
            spacing = min(d_mm / 2.0, 300.0)
        else:
            spacing = av * fy_mpa * d_mm / (vs_needed_kn * 1000.0)
            spacing = max(75.0, min(spacing, d_mm / 2.0, 300.0))
        return StirrupLayout(
            designation=f"{diameter_mm:.0f}M",
            diameter_mm=diameter_mm,
            legs=legs,
            spacing_mm=round(spacing, 1),
            metadata={"Av_mm2": round(av, 1), "width_mm": width_mm},
        )

    def select_slab_mesh(
        self,
        as_required_mm2_per_m: float,
        *,
        thickness_mm: float,
        diameter_mm: float = 12.0,
        max_spacing_mm: float | None = None,
        layer: str = "SLAB_BOTTOM",
    ) -> ReinforcementBarSet:
        limit = max_spacing_mm or min(3.0 * thickness_mm, 450.0)
        area = bar_area_mm2(diameter_mm)
        spacing = min(limit, 1000.0 * area / max(as_required_mm2_per_m, 1.0))
        spacing = max(80.0, min(spacing, limit))
        count = max(1, int(math.floor(1000.0 / spacing)))
        return ReinforcementBarSet(
            designation=f"{diameter_mm:.0f}M",
            diameter_mm=diameter_mm,
            count=count,
            area_each_mm2=round(area, 1),
            spacing_mm=round(spacing, 1),
            layer=layer,
        )
