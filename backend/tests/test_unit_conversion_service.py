"""Unit conversion service tests."""

import pytest

from app.application.exceptions import UnsupportedUnitConversionError
from app.application.unit_conversion_service import UnitConversionService
from app.domain.models.units import EngineeringQuantityType


@pytest.fixture
def service() -> UnitConversionService:
    return UnitConversionService()


def test_convert_length_ft_to_m(service: UnitConversionService) -> None:
    result = service.convert(
        10.0,
        from_unit="ft",
        to_unit="m",
        quantity_type=EngineeringQuantityType.LENGTH,
    )
    assert result.value == pytest.approx(3.048, rel=1e-6)


def test_convert_force_kip_to_kn(service: UnitConversionService) -> None:
    result = service.convert(
        1.0,
        from_unit="kip",
        to_unit="kN",
        quantity_type=EngineeringQuantityType.FORCE,
    )
    assert result.value == pytest.approx(4.4482216153, rel=1e-6)


def test_convert_stress_ksi_to_mpa(service: UnitConversionService) -> None:
    result = service.convert(
        1.0,
        from_unit="ksi",
        to_unit="MPa",
        quantity_type=EngineeringQuantityType.STRESS,
    )
    assert result.value == pytest.approx(6.89475728, rel=1e-6)


def test_convert_round_trip(service: UnitConversionService) -> None:
    original = 25.4
    to_si = service.convert(
        original,
        from_unit="ft",
        to_unit="m",
        quantity_type=EngineeringQuantityType.LENGTH,
    )
    back = service.convert(
        to_si.value,
        from_unit="m",
        to_unit="ft",
        quantity_type=EngineeringQuantityType.LENGTH,
    )
    assert back.value == pytest.approx(original, rel=1e-9)


def test_convert_mm_to_in(service: UnitConversionService) -> None:
    result = service.convert(
        300.0,
        from_unit="mm",
        to_unit="in",
        quantity_type=EngineeringQuantityType.LENGTH,
    )
    assert result.value == pytest.approx(11.811023622, rel=1e-6)


def test_convert_mm2_to_in2(service: UnitConversionService) -> None:
    result = service.convert(
        1500.0,
        from_unit="mm2",
        to_unit="in2",
        quantity_type=EngineeringQuantityType.AREA,
    )
    assert result.value == pytest.approx(2.325003875, rel=1e-6)


def test_unsupported_conversion_raises(service: UnitConversionService) -> None:
    with pytest.raises(UnsupportedUnitConversionError):
        service.convert(
            1.0,
            from_unit="ft",
            to_unit="kip",
            quantity_type=EngineeringQuantityType.LENGTH,
        )
