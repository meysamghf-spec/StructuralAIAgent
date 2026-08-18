"""Unit conversion API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.units import EngineeringQuantityType, UnitConversionResult


class UnitConversionRequest(BaseModel):
    value: float
    from_unit: str = Field(..., min_length=1)
    to_unit: str = Field(..., min_length=1)
    quantity_type: EngineeringQuantityType


class UnitConversionResponse(BaseModel):
    value: float
    from_unit: str
    to_unit: str
    quantity_type: EngineeringQuantityType

    @classmethod
    def from_domain(cls, result: UnitConversionResult) -> UnitConversionResponse:
        return cls.model_validate(result.model_dump())
