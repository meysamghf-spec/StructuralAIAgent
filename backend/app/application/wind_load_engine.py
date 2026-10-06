"""
Preliminary ASCE 7-22 directional MWFRS wind workflow.

Implemented:
* Velocity pressure qz = 0.613 Kz Kzt Kd Ke V^2 (N/m², V in m/s) — ASCE 7-22 §26.10.1
* Exposure B/C/D velocity-pressure exposure coefficient Kz — §26.10.1 / Table 26.10-1
* Kd = 0.85 for MWFRS of buildings — Table 26.6-1
* G = 0.85 for rigid buildings — §26.11.1 (assumed rigid; dynamic G not computed)
* Directional MWFRS wall Cp: windward +0.8, leeward from Table 27.3-1 (L/B) — Ch. 27
* Story forces from net along-wind wall pressure × projected width × tributary height

Not implemented (must not be labelled code-compliant):
* Chapter 28 envelope procedure
* MWFRS roof pressures, parapets, canopy
* Torsional wind cases / partial loading
* Topographic factor Kzt other than 1.0 unless supplied
* Wind tunnel, occupancy Risk Category maps, site-specific basic wind speed
* Flexible-building gust effect factor
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models.pem_architecture import BuildingModel
from app.domain.models.pem_structural import (
    InputOrigin,
    InputProvenance,
    LoadCase,
    LoadCategory,
    LoadDefinition,
    LoadDistribution,
    StoryForce,
    StructuralModel,
)


@dataclass
class WindEngineInputs:
    basic_wind_speed_mps: float = 51.41  # 115 mph
    risk_category: str = "II"
    exposure: str = "C"
    topographic_factor_kzt: float = 1.0
    directionality_factor_kd: float = 0.85
    ground_elevation_factor_ke: float = 1.0
    enclosure: str = "ENCLOSED"
    gust_effect_g: float = 0.85
    speed_origin: InputOrigin = InputOrigin.ASSUMED
    exposure_origin: InputOrigin = InputOrigin.DEFAULT


@dataclass
class WindEngineResult:
    load_cases: list[LoadCase]
    story_forces: list[StoryForce]
    provenance: list[InputProvenance]
    assumptions: list[str]
    warnings: list[str]
    qh_kN_m2: float
    fidelity: str = "PRELIMINARY"


_EXPOSURE = {
    "B": (7.0, 365.76),
    "C": (9.5, 274.32),
    "D": (11.5, 213.36),
}


class WindLoadEngine:
    def generate(
        self,
        building: BuildingModel,
        structural: StructuralModel,
        *,
        inputs: WindEngineInputs | None = None,
    ) -> WindEngineResult:
        cfg = inputs or WindEngineInputs()
        site = building.site
        width_x = float(site.frontage_m) if site is not None else 12.0
        width_y = float(site.depth_m) if site is not None else 22.0
        levels = sorted(structural.geometry.levels, key=lambda item: item.elevation)
        mean_roof = levels[-1].elevation if levels else max((plan.elevation_m for plan in building.floor_plans), default=12.0)
        mean_roof = max(mean_roof, 4.6)
        kz_h = _kz(mean_roof, cfg.exposure)
        qh = _qz(kz_h, cfg)
        cp_lee_x = _leeward_cp(width_x / max(width_y, 1e-6))
        cp_lee_y = _leeward_cp(width_y / max(width_x, 1e-6))

        provenance = [
            InputProvenance(
                field="basic_wind_speed",
                value=f"{cfg.basic_wind_speed_mps:.2f}",
                origin=cfg.speed_origin,
                note="115 mph default when no site wind speed is supplied. Not a mapped ASCE 7 wind speed.",
                unit="m/s",
            ),
            InputProvenance(field="exposure", value=cfg.exposure, origin=cfg.exposure_origin, note="Default Exposure C."),
            InputProvenance(
                field="Kzt",
                value=str(cfg.topographic_factor_kzt),
                origin=InputOrigin.DEFAULT if cfg.topographic_factor_kzt == 1.0 else InputOrigin.USER_PROVIDED,
                note="Flat terrain assumed unless a topographic factor is supplied.",
            ),
            InputProvenance(field="Kd", value=str(cfg.directionality_factor_kd), origin=InputOrigin.DEFAULT, note="Table 26.6-1 MWFRS buildings."),
            InputProvenance(field="enclosure", value=cfg.enclosure, origin=InputOrigin.ASSUMED, note="Enclosed building; GCpi cancels for net horizontal force."),
        ]
        assumptions = [
            "ASCE 7-22 §26.10.1 velocity pressure with Exposure-based Kz and Kd=0.85.",
            "Directional MWFRS wall Cp: windward +0.8; leeward from Table 27.3-1 (L/B). G=0.85 rigid.",
            "Story force = G (qz Cp_w − qh Cp_l) × projected width × tributary storey height.",
            f"Mean roof height h = {mean_roof:.2f} m, qh = {qh:.3f} kN/m².",
        ]
        warnings = [
            "This is a simplified directional MWFRS wall-pressure procedure, not a complete ASCE 7 Chapter 26–27 wind design.",
            "Chapter 28, torsional wind cases, roof MWFRS pressures and a mapped basic wind speed are NOT_IMPLEMENTED.",
            "Do not present these wind loads as a code-compliant wind design.",
        ]

        directions = (
            ("WIND_X+", 1.0, 0.0, width_y, cp_lee_x),
            ("WIND_X-", -1.0, 0.0, width_y, cp_lee_x),
            ("WIND_Y+", 0.0, 1.0, width_x, cp_lee_y),
            ("WIND_Y-", 0.0, -1.0, width_x, cp_lee_y),
        )
        cases: list[LoadCase] = []
        story_forces: list[StoryForce] = []
        elevated = [level for level in levels[1:]] if len(levels) > 1 else levels
        for name, dx, dy, projected_width, cp_lee in directions:
            case = LoadCase(
                id=f"LC-{name}",
                name=name,
                category=LoadCategory.WIND,
                description=f"Simplified ASCE 7-22 directional MWFRS {name}",
                code_reference="ASCE 7-22 §26.10 + §27.3 (walls only, simplified)",
                metadata={"fidelity": "PRELIMINARY", "procedure": "MWFRS_DIRECTIONAL_WALLS", "unit": "kN"},
            )
            for index, level in enumerate(elevated):
                z = max(level.elevation, 4.6)
                kz = _kz(z, cfg.exposure)
                qz = _qz(kz, cfg)
                p_net = cfg.gust_effect_g * (qz * 0.8 - qh * cp_lee)
                h_trib = _tributary_height(elevated, index)
                force = p_net * projected_width * h_trib
                story_forces.append(
                    StoryForce(
                        level_id=level.id,
                        case_id=case.id,
                        fx_kN=round(force * dx, 4),
                        fy_kN=round(force * dy, 4),
                        metadata={"p_net_kN_m2": round(p_net, 4), "qz_kN_m2": round(qz, 4), "h_trib_m": round(h_trib, 4)},
                    )
                )
                case.loads.append(
                    LoadDefinition(
                        id=f"LD-{name}-{level.id}",
                        name=f"{name} at {level.name}",
                        load_case_id=case.id,
                        category=LoadCategory.WIND,
                        distribution=LoadDistribution.NODAL,
                        magnitude=round(abs(force), 4),
                        direction_x=dx,
                        direction_y=dy,
                        direction_z=0.0,
                        unit="kN",
                        metadata={"level_id": level.id, "source": "wind_load_engine", "area": "projected_wall"},
                    )
                )
            cases.append(case)
        return WindEngineResult(
            load_cases=cases,
            story_forces=story_forces,
            provenance=provenance,
            assumptions=assumptions,
            warnings=warnings,
            qh_kN_m2=qh,
        )


def _kz(z_m: float, exposure: str) -> float:
    alpha, zg = _EXPOSURE.get(exposure.upper(), _EXPOSURE["C"])
    z = min(max(z_m, 4.6), zg)
    return 2.01 * (z / zg) ** (2.0 / alpha)


def _qz(kz: float, cfg: WindEngineInputs) -> float:
    return 0.000613 * kz * cfg.topographic_factor_kzt * cfg.directionality_factor_kd * cfg.ground_elevation_factor_ke * cfg.basic_wind_speed_mps**2


def _leeward_cp(aspect: float) -> float:
    if aspect <= 1.0:
        return -0.5
    if aspect >= 4.0:
        return -0.2
    if aspect <= 2.0:
        return -0.5 + (aspect - 1.0) * 0.2
    return -0.3 + (aspect - 2.0) * 0.05


def _tributary_height(levels, index: int) -> float:
    elevations = [item.elevation for item in levels]
    height = 0.0
    if index > 0:
        height += 0.5 * (elevations[index] - elevations[index - 1])
    else:
        height += 0.5 * elevations[index]
    if index < len(elevations) - 1:
        height += 0.5 * (elevations[index + 1] - elevations[index])
    else:
        if index > 0:
            height += 0.5 * (elevations[index] - elevations[index - 1])
        else:
            height += 1.5
    return max(height, 0.5)
