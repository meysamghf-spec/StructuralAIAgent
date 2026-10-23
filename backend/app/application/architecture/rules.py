"""Configurable design rules (Mabhas 4 + typical Iranian municipal rules).

Every number is a default that a project can override (``ArchRules(**overrides)``); the values are the usual
figures used by municipalities / Mabhas 4 (Iranian National Building Regulations, Part 4) for residential buildings
and are documented in the drawing set's assumptions sheet. They are *not* a substitute for the local
comprehensive/detailed plan (طرح تفصیلی) of the city, which the engineer must check.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass
class ArchRules:
    # --- municipal (طرح تفصیلی, typical) ---
    occupancy_pct: float = 60.0            # سطح اشغال: building depth = 60% of plot depth (+ extra)
    occupancy_extra_m: float = 2.0         # common "60% + 2 m" allowance (set 0 where not allowed)
    max_floors_default: int = 5
    parking_per_unit: float = 1.0          # one stall per unit
    stall_w_m: float = 2.5
    stall_l_m: float = 5.0
    driveway_w_m: float = 3.0
    pilotis_ground_floor: bool = True      # ground floor = parking (پیلوت) when parking is required
    side_setback_m: float = 0.0            # attached (پیوسته) urban fabric by default
    # --- Mabhas 4 (typical residential minima) ---
    floor_to_floor_m: float = 3.20
    ground_floor_to_floor_m: float = 3.00
    min_clear_height_m: float = 2.60
    slab_thickness_m: float = 0.30
    parapet_m: float = 1.10                 # roof guard height
    stair_width_m: float = 1.20             # flight width (≥1.10 typical for small residential)
    riser_m: float = 0.17
    tread_m: float = 0.28
    elevator_from_floors: int = 4           # elevator when ≥ this many floors above ground (configurable; Mabhas 15/4)
    elevator_car_m: tuple[float, float] = (1.10, 1.40)
    elevator_shaft_m: tuple[float, float] = (1.70, 1.80)
    min_bedroom_m2: float = 7.5
    min_master_bedroom_m2: float = 9.0
    min_living_m2: float = 12.0
    min_kitchen_m2: float = 5.0
    min_bath_m2: float = 2.5
    min_corridor_w_m: float = 1.10
    exterior_wall_m: float = 0.35
    interior_wall_m: float = 0.12
    party_wall_m: float = 0.25
    balcony_depth_m: float = 1.20
    entrance_door_w_m: float = 1.00
    room_door_w_m: float = 0.90
    wet_door_w_m: float = 0.70
    window_sill_m: float = 0.90
    window_head_m: float = 2.30
    wet_window_sill_m: float = 1.60
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_overrides(cls, overrides: dict[str, Any] | None) -> "ArchRules":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (overrides or {}).items() if k in names})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def occupancy_depth(self, plot_depth_m: float) -> float:
        return min(plot_depth_m, plot_depth_m * self.occupancy_pct / 100.0 + self.occupancy_extra_m)
