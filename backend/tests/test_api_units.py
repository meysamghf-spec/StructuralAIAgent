"""API tests — unit conversion endpoint."""

import pytest
from fastapi.testclient import TestClient


def test_api_convert_units(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/units/convert",
        json={
            "value": 12.0,
            "from_unit": "ft",
            "to_unit": "m",
            "quantity_type": "LENGTH",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["value"] == pytest.approx(3.6576, rel=1e-6)
    assert body["from_unit"] == "ft"
    assert body["to_unit"] == "m"


def test_api_convert_units_invalid_pair(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/units/convert",
        json={
            "value": 1.0,
            "from_unit": "ft",
            "to_unit": "unknown",
            "quantity_type": "LENGTH",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_UNIT_CONVERSION"
