"""Engineering unit types for centralized conversion."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class EngineeringQuantityType(StrEnum):
    LENGTH = "LENGTH"
    FORCE = "FORCE"
    STRESS = "STRESS"
    MOMENT = "MOMENT"
    AREA = "AREA"
    VOLUME = "VOLUME"


class UnitConversionResult(BaseModel):
    value: float
    from_unit: str
    to_unit: str
    quantity_type: EngineeringQuantityType
