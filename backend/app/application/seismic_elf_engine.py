"""
Preliminary ASCE 7-22 Equivalent Lateral Force (ELF) procedure.

Implemented:
* Site coefficients Fa, Fv for Site Class D (Tables 11.4-1 / 11.4-2 interpolated)
* SDS = (2/3) Fa Ss, SD1 = (2/3) Fv S1 — §11.4.5
* Approximate seismic design category from Tables 11.6-1 and 11.6-2 (Risk Cat II)
* Cs = SDS / (R/Ie) with §12.8.1.1 min/max
* Approximate period T = Ct hn^x — Table 12.8-2 (concrete moment frame)
* Base shear V = Cs W — §12.8.1
* Vertical distribution Fx = Cvx V — §12.8.3

Not implemented:
* Site-specific Ss/S1 (must be supplied or clearly ASSUMED)
* Site classes other than B/C/D tabulated here
* Modal response spectrum, accidental torsion 5%, redundancy ρ
* Overstrength vertical seismic, ELF exceptions, seismic detailing
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.pem_architecture import BuildingModel
from app.domain.models.pem_structural import (
    InputOrigin,
    InputProvenance,
    LoadCase,
    LoadCategory,
    LoadDefinition,
    LoadDistribution,
    StoryForce,
    StoryMass,
    StructuralModel,
)


@dataclass
class SeismicEngineInputs:
    ss: float = 1.0
    s1: float = 0.40
    site_class: str = "D"
    risk_category: str = "II"
    importance_ie: float = 1.0
    response_modification_r: float = 5.0
    deflection_amplification_cd: float = 4.5
    structural_system: str = "INTERMEDIATE_RC_MOMENT_FRAME"
    ss_origin: InputOrigin = InputOrigin.ASSUMED
    s1_origin: InputOrigin = InputOrigin.ASSUMED
    r_origin: InputOrigin = InputOrigin.DEFAULT


@dataclass
class SeismicEngineResult:
    load_cases: list[LoadCase]
    story_forces: list[StoryForce]
    provenance: list[InputProvenance]
    assumptions: list[str]
    warnings: list[str]
    sds: float
    sd1: float
    cs: float
    period_s: float
    base_shear_kN: float
    seismic_design_category: str
    fidelity: str = "PRELIMINARY"


_FA_D = ((0.25, 1.6), (0.50, 1.4), (0.75, 1.2), (1.00, 1.1), (1.25, 1.0))
_FV_D = ((0.10, 2.4), (0.20, 2.0), (0.30, 1.8), (0.40, 1.6), (0.50, 1.4))
_FA_C = ((0.25, 1.2), (0.50, 1.2), (0.75, 1.1), (1.00, 1.0), (1.25, 1.0))
_FV_C = ((0.10, 1.7), (0.20, 1.6), (0.30, 1.5), (0.40, 1.4), (0.50, 1.3))
_FA_B = ((0.25, 1.0), (1.25, 1.0))
_FV_B = ((0.10, 1.0), (0.50, 1.0))


class SeismicElfEngine:
    def generate(
        self,
        building: BuildingModel,
        structural: StructuralModel,
        story_masses: list[StoryMass],
        *,
        inputs: SeismicEngineInputs | None = None,
    ) -> SeismicEngineResult:
        cfg = inputs or SeismicEngineInputs()
        fa = _interpolate(cfg.ss, _fa_table(cfg.site_class))
        fv = _interpolate(cfg.s1, _fv_table(cfg.site_class))
        sds = (2.0 / 3.0) * fa * cfg.ss
        sd1 = (2.0 / 3.0) * fv * cfg.s1
        sdc = _seismic_design_category(sds, sd1)

        levels = sorted(structural.geometry.levels, key=lambda item: item.elevation)
        hn = levels[-1].elevation if levels else 12.0
        ct, exponent = 0.0466, 0.9  # Table 12.8-2 concrete moment-resisting frames, hn in metres
        period = ct * max(hn, 1.0) ** exponent
        cs = sds / (cfg.response_modification_r / cfg.importance_ie)
        cs_max = sd1 / max(period * (cfg.response_modification_r / cfg.importance_ie), 1e-9)
        cs = min(cs, cs_max)
        cs_min = max(0.044 * sds * cfg.importance_ie, 0.01)
        if cfg.s1 >= 0.6:
            cs_min = max(cs_min, 0.5 * cfg.s1 / (cfg.response_modification_r / cfg.importance_ie))
        cs = max(cs, cs_min)

        elevated = [level for level in levels[1:]] if len(levels) > 1 else levels
        elevated_ids = {level.id for level in elevated}
        weight = sum(item.seismic_weight_kN for item in story_masses if item.level_id in elevated_ids) or 1.0
        base_shear = cs * weight
        k_exp = 1.0 if period <= 0.5 else 2.0 if period >= 2.5 else 1.0 + (period - 0.5) / 2.0
        mass_by_level = {item.level_id: item for item in story_masses}
        weights = []
        for level in elevated:
            mass = mass_by_level.get(level.id)
            w_i = mass.seismic_weight_kN if mass is not None else 0.0
            weights.append((level, w_i, level.elevation ** k_exp))
        denom = sum(w * hexp for _level, w, hexp in weights) or 1.0

        provenance = [
            InputProvenance(
                field="Ss",
                value=str(cfg.ss),
                origin=cfg.ss_origin,
                note="Not a USGS/site-specific mapped acceleration. Replace with the project geohazard report.",
            ),
            InputProvenance(field="S1", value=str(cfg.s1), origin=cfg.s1_origin, note="Assumed mapped 1 s acceleration."),
            InputProvenance(field="site_class", value=cfg.site_class, origin=InputOrigin.ASSUMED, note="Site Class D assumed when no geotechnical site class is provided."),
            InputProvenance(field="R", value=str(cfg.response_modification_r), origin=cfg.r_origin, note="Intermediate RC moment frame, ASCE 7-22 Table 12.2-1."),
            InputProvenance(field="Ie", value=str(cfg.importance_ie), origin=InputOrigin.DEFAULT, note="Risk Category II."),
        ]
        assumptions = [
            f"ELF §12.8: SDS={sds:.3f}, SD1={sd1:.3f}, T≈{period:.3f} s, Cs={cs:.4f}, SDC={sdc}.",
            f"Seismic weight W = {weight:.1f} kN (dead + partitions; residential live-load mass = 0 per §12.7.2).",
            f"Base shear V = Cs W = {base_shear:.2f} kN. Vertical distribution k={k_exp:.2f}.",
            "Accidental torsion (5% of plan dimension) is NOT included.",
        ]
        warnings = [
            "Ss and S1 are ASSUMED project defaults unless the user supplied mapped values. They are not site-specific.",
            "This is a preliminary ELF workflow, not a complete ASCE 7 Chapter 12 seismic design.",
            "Modal analysis, accidental torsion, redundancy and seismic detailing are NOT_IMPLEMENTED.",
        ]

        story_forces: list[StoryForce] = []
        cases: list[LoadCase] = []
        directions = (("EQ_X+", 1.0, 0.0), ("EQ_X-", -1.0, 0.0), ("EQ_Y+", 0.0, 1.0), ("EQ_Y-", 0.0, -1.0))
        for name, dx, dy in directions:
            case = LoadCase(
                id=f"LC-{name}",
                name=name,
                category=LoadCategory.SEISMIC,
                description=f"ASCE 7-22 ELF {name}",
                code_reference="ASCE 7-22 §12.8 Equivalent Lateral Force (preliminary)",
                metadata={"fidelity": "PRELIMINARY", "Cs": cs, "V_kN": round(base_shear, 4), "SDC": sdc},
            )
            for level, w_i, hexp in weights:
                cux = (w_i * hexp) / denom
                force = cux * base_shear
                story_forces.append(
                    StoryForce(
                        level_id=level.id,
                        case_id=case.id,
                        fx_kN=round(force * dx, 4),
                        fy_kN=round(force * dy, 4),
                        metadata={"Cvx": round(cux, 5), "W_i_kN": round(w_i, 3)},
                    )
                )
                case.loads.append(
                    LoadDefinition(
                        id=f"LD-{name}-{level.id}",
                        name=f"{name} at {level.name}",
                        load_case_id=case.id,
                        category=LoadCategory.SEISMIC,
                        distribution=LoadDistribution.NODAL,
                        magnitude=round(abs(force), 4),
                        direction_x=dx,
                        direction_y=dy,
                        direction_z=0.0,
                        unit="kN",
                        metadata={"level_id": level.id, "source": "seismic_elf_engine"},
                    )
                )
            cases.append(case)
        return SeismicEngineResult(
            load_cases=cases,
            story_forces=story_forces,
            provenance=provenance,
            assumptions=assumptions,
            warnings=warnings,
            sds=sds,
            sd1=sd1,
            cs=cs,
            period_s=period,
            base_shear_kN=base_shear,
            seismic_design_category=sdc,
        )


def _fa_table(site_class: str):
    key = site_class.upper()
    if key == "B":
        return _FA_B
    if key == "C":
        return _FA_C
    return _FA_D


def _fv_table(site_class: str):
    key = site_class.upper()
    if key == "B":
        return _FV_B
    if key == "C":
        return _FV_C
    return _FV_D


def _interpolate(x: float, table: tuple[tuple[float, float], ...]) -> float:
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:], strict=False):
        if x0 <= x <= x1:
            if abs(x1 - x0) < 1e-12:
                return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


def _seismic_design_category(sds: float, sd1: float) -> str:
    def from_sds() -> str:
        if sds < 0.167:
            return "A"
        if sds < 0.33:
            return "B"
        if sds < 0.50:
            return "C"
        return "D"

    def from_sd1() -> str:
        if sd1 < 0.067:
            return "A"
        if sd1 < 0.133:
            return "B"
        if sd1 < 0.20:
            return "C"
        return "D"

    return max(from_sds(), from_sd1())
