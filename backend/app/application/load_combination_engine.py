"""
Centralised load-combination engine.

Combinations are produced once from the selected loading standard and then reused
by analysis and design. Each directional WIND/EQ case gets its own combinations.
PARTITION is combined with DEAD at the dead-load factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models.pem_structural import LoadCase, LoadCategory, LoadCombination, LoadCombinationTerm


@dataclass
class CombinationSpec:
    name: str
    combination_type: str
    factors: dict[LoadCategory, float]
    code_source: str
    fidelity: str
    notes: str = ""


@dataclass
class CombinationEngineResult:
    combinations: list[LoadCombination]
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_ASCE_7_22_STRENGTH: tuple[CombinationSpec, ...] = (
    CombinationSpec(
        name="1.4D",
        combination_type="STRENGTH",
        factors={LoadCategory.DEAD: 1.4},
        code_source="ASCE 7-22 §2.3.1 (2.3.1.1)",
        fidelity="CODE",
    ),
    CombinationSpec(
        name="1.2D + 1.6L + 0.5Lr",
        combination_type="STRENGTH",
        factors={LoadCategory.DEAD: 1.2, LoadCategory.LIVE: 1.6, LoadCategory.ROOF: 0.5},
        code_source="ASCE 7-22 §2.3.1 (2.3.1.2)",
        fidelity="CODE",
    ),
    CombinationSpec(
        name="1.2D + 1.0L + 1.6Lr",
        combination_type="STRENGTH",
        factors={LoadCategory.DEAD: 1.2, LoadCategory.LIVE: 1.0, LoadCategory.ROOF: 1.6},
        code_source="ASCE 7-22 §2.3.1 (2.3.1.3)",
        fidelity="CODE",
    ),
    CombinationSpec(
        name="1.2D + 1.0W + 1.0L + 0.5Lr",
        combination_type="STRENGTH",
        factors={
            LoadCategory.DEAD: 1.2,
            LoadCategory.WIND: 1.0,
            LoadCategory.LIVE: 1.0,
            LoadCategory.ROOF: 0.5,
        },
        code_source="ASCE 7-22 §2.3.1 (2.3.1.4) — wind from simplified MWFRS walls",
        fidelity="PRELIMINARY",
        notes="Wind magnitude uses the simplified directional MWFRS wall procedure, not full Chapter 26–27.",
    ),
    CombinationSpec(
        name="0.9D + 1.0W",
        combination_type="STRENGTH",
        factors={LoadCategory.DEAD: 0.9, LoadCategory.WIND: 1.0},
        code_source="ASCE 7-22 §2.3.1 (2.3.1.6) — wind from simplified MWFRS walls",
        fidelity="PRELIMINARY",
        notes="Wind magnitude uses the simplified directional MWFRS wall procedure, not full Chapter 26–27.",
    ),
    CombinationSpec(
        name="1.2D + 1.0E + 1.0L",
        combination_type="STRENGTH",
        factors={LoadCategory.DEAD: 1.2, LoadCategory.SEISMIC: 1.0, LoadCategory.LIVE: 1.0},
        code_source="ASCE 7-22 §2.3.6 (simplified) with ELF seismic forces",
        fidelity="PRELIMINARY",
        notes="Seismic magnitude uses the preliminary ASCE 7-22 ELF procedure.",
    ),
    CombinationSpec(
        name="0.9D + 1.0E",
        combination_type="STRENGTH",
        factors={LoadCategory.DEAD: 0.9, LoadCategory.SEISMIC: 1.0},
        code_source="ASCE 7-22 §2.3.6 (simplified) with ELF seismic forces",
        fidelity="PRELIMINARY",
        notes="Seismic magnitude uses the preliminary ASCE 7-22 ELF procedure.",
    ),
)

_GRAVITY_GOVERNING = "1.2D + 1.6L + 0.5Lr"
_DEAD_LIKE = (LoadCategory.DEAD, LoadCategory.PARTITION)


class LoadCombinationEngine:
    def generate(
        self,
        load_cases: list[LoadCase],
        *,
        standard: str = "ASCE 7-22",
    ) -> CombinationEngineResult:
        by_category: dict[LoadCategory, list[LoadCase]] = {}
        for case in load_cases:
            by_category.setdefault(case.category, []).append(case)
        assumptions = [
            f"Load combinations generated from {standard} strength combinations. "
            "ACI 318-25 uses these combination demands for member checks. "
            "PARTITION is included with the DEAD factor. Each WIND/EQ direction is combined separately."
        ]
        warnings: list[str] = []
        combinations: list[LoadCombination] = []
        index = 0

        for spec in _ASCE_7_22_STRENGTH:
            wind_cases = by_category.get(LoadCategory.WIND, [])
            eq_cases = by_category.get(LoadCategory.SEISMIC, [])
            directional: list[LoadCase | None] = [None]
            suffix = ""
            if LoadCategory.WIND in spec.factors:
                if not wind_cases:
                    continue
                directional = wind_cases
            elif LoadCategory.SEISMIC in spec.factors:
                if not eq_cases:
                    continue
                directional = eq_cases

            for extra in directional:
                terms: list[LoadCombinationTerm] = []
                skipped = False
                for category, factor in spec.factors.items():
                    if category in _DEAD_LIKE or category is LoadCategory.DEAD:
                        dead_cases = []
                        for dead_cat in _DEAD_LIKE:
                            dead_cases.extend(by_category.get(dead_cat, []))
                        if not dead_cases:
                            skipped = True
                            break
                        for case in dead_cases:
                            terms.append(LoadCombinationTerm(load_case_id=case.id, factor=factor))
                        continue
                    if category in (LoadCategory.WIND, LoadCategory.SEISMIC):
                        if extra is None:
                            skipped = True
                            break
                        terms.append(LoadCombinationTerm(load_case_id=extra.id, factor=factor))
                        suffix = f" ({extra.name})"
                        continue
                    cases = by_category.get(category, [])
                    if not cases:
                        if category is LoadCategory.ROOF:
                            skipped = True
                            break
                        skipped = True
                        break
                    terms.append(LoadCombinationTerm(load_case_id=cases[0].id, factor=factor))
                if skipped or not terms:
                    continue
                if spec.fidelity == "PRELIMINARY":
                    warnings.append(
                        f"Combination '{spec.name}{suffix}' is labelled PRELIMINARY: {spec.notes or spec.code_source}"
                    )
                index += 1
                combinations.append(
                    LoadCombination(
                        id=f"COMB-{index}",
                        name=f"{spec.name}{suffix}",
                        combination_type=spec.combination_type,
                        terms=terms,
                        code_source=spec.code_source,
                        metadata={
                            "fidelity": spec.fidelity,
                            "standard": standard,
                            "governing_gravity": spec.name == _GRAVITY_GOVERNING and extra is None,
                            "notes": spec.notes,
                            "lateral_case_id": extra.id if extra is not None else None,
                        },
                    )
                )

        if not combinations:
            warnings.append("No load combinations could be formed from the available load cases.")
        return CombinationEngineResult(
            combinations=combinations,
            assumptions=assumptions,
            warnings=warnings,
        )

    @staticmethod
    def governing_gravity_combination(combinations: list[LoadCombination]) -> LoadCombination | None:
        for combination in combinations:
            if combination.metadata.get("governing_gravity"):
                return combination
        return combinations[0] if combinations else None
