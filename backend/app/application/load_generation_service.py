"""
Preliminary gravity-load generator plus deterministic wind/seismic cases.

Gravity intensities come from geometry and ASCE 7-22 live-load tables.
Wind uses WindLoadEngine (simplified ASCE 7-22 MWFRS walls).
Seismic uses SeismicElfEngine (simplified ASCE 7-22 ELF).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.mass_model_service import MassModelService
from app.application.seismic_elf_engine import SeismicElfEngine
from app.application.wind_load_engine import WindLoadEngine
from app.domain.models.pem_architecture import BuildingModel, FloorType
from app.domain.models.pem_structural import (
    InputProvenance,
    LoadCase,
    LoadCategory,
    LoadDefinition,
    LoadDistribution,
    StoryForce,
    StoryMass,
    StructuralModel,
    MemberType,
)


@dataclass
class LoadGenerationDefaults:
    residential_live_kn_m2: float = 1.92  # 40 psf, ASCE 7-22 Table 4.3-1 residential
    parking_live_kn_m2: float = 1.92  # 40 psf garages
    roof_live_kn_m2: float = 0.96  # 20 psf ordinary flat roof
    floor_finish_kn_m2: float = 1.00
    partition_kn_m2: float = 1.00
    superimposed_kn_m2: float = 0.50
    roof_finish_kn_m2: float = 0.50
    concrete_density_kn_m3: float = 25.0
    default_slab_thickness_m: float = 0.15


@dataclass
class LoadGenerationResult:
    load_cases: list[LoadCase]
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fidelity: dict[str, str] = field(default_factory=dict)
    story_forces: list[StoryForce] = field(default_factory=list)
    story_masses: list[StoryMass] = field(default_factory=list)
    provenance: list[InputProvenance] = field(default_factory=list)


class LoadGenerationService:
    def __init__(self, defaults: LoadGenerationDefaults | None = None) -> None:
        self._d = defaults or LoadGenerationDefaults()
        self._wind = WindLoadEngine()
        self._seismic = SeismicElfEngine()
        self._mass = MassModelService()

    def generate(self, building: BuildingModel, structural: StructuralModel) -> LoadGenerationResult:
        slab_thickness = self._slab_thickness(structural)
        self_weight = slab_thickness * self._d.concrete_density_kn_m3
        dead_residential = self_weight + self._d.floor_finish_kn_m2 + self._d.superimposed_kn_m2
        dead_parking = self_weight + self._d.floor_finish_kn_m2 + self._d.superimposed_kn_m2
        dead_roof = self_weight + self._d.roof_finish_kn_m2

        assumptions = [
            f"Slab self-weight = {slab_thickness:.3f} m × {self._d.concrete_density_kn_m3:.1f} kN/m³ "
            f"= {self_weight:.2f} kN/m² (normalweight concrete).",
            f"Residential floor dead load (excluding partitions) = {dead_residential:.2f} kN/m².",
            f"Partition load = {self._d.partition_kn_m2:.2f} kN/m² as its own PARTITION case (treated as dead in combinations).",
            f"Residential live load = {self._d.residential_live_kn_m2:.2f} kN/m² "
            "(ASCE 7-22 Table 4.3-1, private rooms and corridors serving them, 40 psf).",
            f"Parking live load = {self._d.parking_live_kn_m2:.2f} kN/m² "
            "(ASCE 7-22 Table 4.3-1 passenger-vehicle garages, 40 psf).",
            f"Roof live load = {self._d.roof_live_kn_m2:.2f} kN/m² "
            "(ASCE 7-22 Table 4.8-1 ordinary flat roofs, 20 psf, unreduced).",
        ]
        warnings = [
            "Live-load reduction (ASCE 7-22 4.7) is not applied.",
            "Beam and column self-weight are added as line loads during analysis from member sections.",
        ]

        dead = LoadCase(
            id="LC-DEAD",
            name="DEAD",
            category=LoadCategory.DEAD,
            description="Gravity dead load from self-weight, finishes and superimposed",
            code_reference="ASCE 7-22 Chapter 3 (self-weight) — intensities from geometry",
            metadata={"fidelity": "PRELIMINARY", "unit": "kN/m2"},
        )
        partition = LoadCase(
            id="LC-PARTITION",
            name="PARTITION",
            category=LoadCategory.PARTITION,
            description="Partition load, combined with dead",
            code_reference="ASCE 7-22 §4.3.2 / occupancy partitions",
            metadata={"fidelity": "PRELIMINARY", "unit": "kN/m2"},
        )
        live = LoadCase(
            id="LC-LIVE",
            name="LIVE",
            category=LoadCategory.LIVE,
            description="Occupancy live load",
            code_reference="ASCE 7-22 Table 4.3-1",
            metadata={"fidelity": "CODE_TABLE", "unit": "kN/m2"},
        )
        roof = LoadCase(
            id="LC-ROOF",
            name="ROOF",
            category=LoadCategory.ROOF,
            description="Roof live load",
            code_reference="ASCE 7-22 Table 4.8-1",
            metadata={"fidelity": "CODE_TABLE", "unit": "kN/m2"},
        )

        for member in structural.members.members:
            if member.member_type is not MemberType.SLAB or member.area_id is None:
                continue
            floor_type = str(member.metadata.get("floor_type", FloorType.RESIDENTIAL.value))
            area = float(member.metadata.get("area_m2") or 0.0)
            level_id = member.level_id
            if floor_type == FloorType.ROOF.value:
                dead_intensity = dead_roof
                live_case, live_intensity = roof, self._d.roof_live_kn_m2
                apply_partition = False
            elif floor_type in (FloorType.PARKING.value, FloorType.PILOTI.value):
                dead_intensity = dead_parking
                live_case, live_intensity = live, self._d.parking_live_kn_m2
                apply_partition = False
            else:
                dead_intensity = dead_residential
                live_case, live_intensity = live, self._d.residential_live_kn_m2
                apply_partition = True

            dead.loads.append(
                self._area_load(
                    load_id=f"LD-D-{member.id}",
                    name=f"Dead on {member.name}",
                    load_case_id=dead.id,
                    category=LoadCategory.DEAD,
                    magnitude=dead_intensity,
                    area_id=member.area_id,
                    member_id=member.id,
                    area_m2=area,
                    level_id=level_id,
                    occupancy=floor_type,
                )
            )
            live_case.loads.append(
                self._area_load(
                    load_id=f"LD-L-{member.id}",
                    name=f"Live on {member.name}",
                    load_case_id=live_case.id,
                    category=live_case.category,
                    magnitude=live_intensity,
                    area_id=member.area_id,
                    member_id=member.id,
                    area_m2=area,
                    occupancy=floor_type,
                    level_id=level_id,
                )
            )
            if apply_partition:
                partition.loads.append(
                    self._area_load(
                        load_id=f"LD-P-{member.id}",
                        name=f"Partitions on {member.name}",
                        load_case_id=partition.id,
                        category=LoadCategory.PARTITION,
                        magnitude=self._d.partition_kn_m2,
                        area_id=member.area_id,
                        member_id=member.id,
                        area_m2=area,
                        occupancy=floor_type,
                        level_id=level_id,
                    )
                )

        structural.load_cases = [dead, live, roof, partition]
        mass = self._mass.generate(structural)
        wind = self._wind.generate(building, structural)
        seismic = self._seismic.generate(building, structural, mass.story_masses)

        assumptions.extend(mass.assumptions)
        assumptions.extend(wind.assumptions)
        assumptions.extend(seismic.assumptions)
        warnings.extend(wind.warnings)
        warnings.extend(seismic.warnings)

        return LoadGenerationResult(
            load_cases=[dead, partition, live, roof, *wind.load_cases, *seismic.load_cases],
            assumptions=assumptions,
            warnings=warnings,
            fidelity={
                "DEAD": "PRELIMINARY",
                "PARTITION": "PRELIMINARY",
                "LIVE": "CODE_TABLE",
                "ROOF": "CODE_TABLE",
                "WIND": "PRELIMINARY",
                "SEISMIC": "PRELIMINARY",
            },
            story_forces=wind.story_forces + seismic.story_forces,
            story_masses=mass.story_masses,
            provenance=wind.provenance + seismic.provenance,
        )

    @staticmethod
    def _area_load(
        *,
        load_id: str,
        name: str,
        load_case_id: str,
        category: LoadCategory,
        magnitude: float,
        area_id: str,
        member_id: str,
        area_m2: float,
        occupancy: str | None = None,
        level_id: str | None = None,
    ) -> LoadDefinition:
        return LoadDefinition(
            id=load_id,
            name=name,
            load_case_id=load_case_id,
            category=category,
            distribution=LoadDistribution.AREA,
            magnitude=round(magnitude, 4),
            direction_x=0.0,
            direction_y=0.0,
            direction_z=-1.0,
            unit="kN/m2",
            area_id=area_id,
            member_id=member_id,
            metadata={
                "area_m2": round(area_m2, 4),
                "resultant_kN": round(magnitude * area_m2, 4),
                "occupancy": occupancy,
                "level_id": level_id,
                "source": "load_generation_service",
            },
        )

    def _slab_thickness(self, structural: StructuralModel) -> float:
        if structural.sections.slabs:
            return float(structural.sections.slabs[0].thickness or self._d.default_slab_thickness_m)
        return self._d.default_slab_thickness_m
