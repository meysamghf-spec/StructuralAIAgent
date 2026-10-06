"""Centralized deterministic engineering unit conversion."""

from __future__ import annotations

from app.application.exceptions import UnsupportedUnitConversionError
from app.domain.models.units import EngineeringQuantityType, UnitConversionResult

# Factors to SI base units: m, N, Pa, N·m, m², m³
_TO_SI: dict[EngineeringQuantityType, dict[str, float]] = {
    EngineeringQuantityType.LENGTH: {
        "m": 1.0,
        "mm": 0.001,
        "ft": 0.3048,
        "in": 0.0254,
    },
    EngineeringQuantityType.FORCE: {
        "n": 1.0,
        "kn": 1000.0,
        "kip": 4448.2216153,
        "lb": 4.4482216153,
    },
    EngineeringQuantityType.STRESS: {
        "pa": 1.0,
        "mpa": 1_000_000.0,
        "ksi": 6_894_757.28,
        "psi": 6894.75728,
    },
    EngineeringQuantityType.MOMENT: {
        "n·m": 1.0,
        "n-m": 1.0,
        "kn·m": 1000.0,
        "kn-m": 1000.0,
        "kip-ft": 1355.8179483,
        "kip-in": 112.984829025,
    },
    EngineeringQuantityType.AREA: {
        "m2": 1.0,
        "mm2": 1e-6,
        "in2": 0.00064516,
        "ft2": 0.09290304,
    },
    EngineeringQuantityType.VOLUME: {
        "m3": 1.0,
        "cm3": 1e-6,
        "mm3": 1e-9,
        "ft3": 0.0283168466,
        "in3": 1.6387064e-5,
    },
}


class UnitConversionService:
    def convert(
        self,
        value: float,
        *,
        from_unit: str,
        to_unit: str,
        quantity_type: EngineeringQuantityType,
    ) -> UnitConversionResult:
        normalized_from = _normalize_unit(from_unit)
        normalized_to = _normalize_unit(to_unit)
        table = _TO_SI.get(quantity_type)
        if table is None:
            raise UnsupportedUnitConversionError(
                from_unit=from_unit,
                to_unit=to_unit,
                quantity_type=quantity_type.value,
            )

        if normalized_from not in table or normalized_to not in table:
            raise UnsupportedUnitConversionError(
                from_unit=from_unit,
                to_unit=to_unit,
                quantity_type=quantity_type.value,
            )

        si_value = value * table[normalized_from]
        converted = si_value / table[normalized_to]
        return UnitConversionResult(
            value=converted,
            from_unit=from_unit,
            to_unit=to_unit,
            quantity_type=quantity_type,
        )

    def supported_units(self, quantity_type: EngineeringQuantityType) -> list[str]:
        table = _TO_SI.get(quantity_type, {})
        return sorted(table.keys())


def _normalize_unit(unit: str) -> str:
    return unit.strip().lower().replace(" ", "")
