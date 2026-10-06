"""Deterministic storey mass source derived from gravity load cases."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models.pem_structural import LoadCategory, MemberType, StoryMass, StructuralModel

G_MPS2 = 9.80665
# ASCE 7-22 §12.7.2: typically 0% of residential live load in seismic weight.
RESIDENTIAL_LIVE_MASS_FACTOR = 0.0


@dataclass
class MassModelResult:
    story_masses: list[StoryMass]
    total_seismic_weight_kN: float
    assumptions: list[str]
    live_mass_factor: float = RESIDENTIAL_LIVE_MASS_FACTOR


class MassModelService:
    def generate(self, structural: StructuralModel, *, live_mass_factor: float = RESIDENTIAL_LIVE_MASS_FACTOR) -> MassModelResult:
        by_level: dict[str, dict[str, float]] = {}
        for case in structural.load_cases:
            if case.category not in (LoadCategory.DEAD, LoadCategory.PARTITION, LoadCategory.LIVE, LoadCategory.ROOF):
                continue
            for load in case.loads:
                level_id = str((load.metadata or {}).get("level_id") or "")
                if not level_id:
                    member = next((item for item in structural.members.members if item.id == load.member_id), None)
                    if member is not None:
                        level_id = member.level_id or ""
                if not level_id:
                    continue
                area = float((load.metadata or {}).get("area_m2") or 0.0)
                resultant = float((load.metadata or {}).get("resultant_kN") or (load.magnitude * area))
                bucket = by_level.setdefault(level_id, {"dead": 0.0, "live": 0.0, "partition": 0.0})
                if case.category in (LoadCategory.DEAD,):
                    bucket["dead"] += resultant
                elif case.category is LoadCategory.PARTITION:
                    bucket["partition"] += resultant
                else:
                    bucket["live"] += resultant

        # Column/beam self-weight is not always on area loads; add from sections if a level has slabs.
        self_weight = _member_self_weight_by_level(structural)
        masses: list[StoryMass] = []
        for level in structural.geometry.levels:
            bucket = by_level.get(level.id, {"dead": 0.0, "live": 0.0, "partition": 0.0})
            dead = bucket["dead"] + bucket["partition"] + self_weight.get(level.id, 0.0)
            live = bucket["live"]
            seismic = dead + live_mass_factor * live
            masses.append(
                StoryMass(
                    level_id=level.id,
                    dead_weight_kN=round(dead, 3),
                    live_weight_kN=round(live, 3),
                    seismic_weight_kN=round(seismic, 3),
                    mass_kg=round(seismic * 1000.0 / G_MPS2, 1),
                    assumptions=[
                        f"Live-load mass factor = {live_mass_factor:.2f} (residential default 0 per ASCE 7-22 §12.7.2).",
                    ],
                    metadata={"g_mps2": G_MPS2, "prepared_for": "future_modal_analysis"},
                )
            )
        total = sum(item.seismic_weight_kN for item in masses)
        return MassModelResult(
            story_masses=masses,
            total_seismic_weight_kN=total,
            assumptions=[
                "Storey mass = (dead + partitions + live_mass_factor × live) / g.",
                "Prepared for future modal analysis; only ELF uses these masses today.",
            ],
            live_mass_factor=live_mass_factor,
        )


def _member_self_weight_by_level(structural: StructuralModel) -> dict[str, float]:
    points = {point.id: point for point in structural.geometry.points}
    sections = {
        **{item.id: item for item in structural.sections.beams},
        **{item.id: item for item in structural.sections.columns},
    }
    materials = {item.id: item for item in structural.materials.concrete}
    by_level: dict[str, float] = {}
    for member in structural.members.members:
        if member.member_type not in (MemberType.BEAM, MemberType.COLUMN):
            continue
        section = sections.get(member.section_id)
        material = materials.get(member.material_id)
        if section is None or material is None or member.start_point_id is None or member.end_point_id is None:
            continue
        start = points.get(member.start_point_id)
        end = points.get(member.end_point_id)
        if start is None or end is None:
            continue
        length = ((end.x - start.x) ** 2 + (end.y - start.y) ** 2 + (end.z - start.z) ** 2) ** 0.5
        width = float(getattr(section, "width", 0.3) or 0.3)
        depth = float(getattr(section, "depth", 0.5) or 0.5)
        unit_weight = float(material.unit_weight or 25.0)
        weight = unit_weight * width * depth * length
        level_id = member.level_id or end.level_id or ""
        if level_id:
            by_level[level_id] = by_level.get(level_id, 0.0) + weight
    return by_level
