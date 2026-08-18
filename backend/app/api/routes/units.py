"""Unit conversion REST endpoints — /api/v1/units."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_unit_conversion_service
from app.api.schemas.units import UnitConversionRequest, UnitConversionResponse
from app.application.unit_conversion_service import UnitConversionService

router = APIRouter(prefix="/units", tags=["units"])


@router.post("/convert", response_model=UnitConversionResponse)
def convert_units(
    body: UnitConversionRequest,
    conversion_service: Annotated[UnitConversionService, Depends(get_unit_conversion_service)],
) -> UnitConversionResponse:
    result = conversion_service.convert(
        body.value,
        from_unit=body.from_unit,
        to_unit=body.to_unit,
        quantity_type=body.quantity_type,
    )
    return UnitConversionResponse.from_domain(result)
