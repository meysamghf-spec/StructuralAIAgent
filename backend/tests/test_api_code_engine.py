"""API tests — CodeEngine endpoints."""

from fastapi.testclient import TestClient


def test_api_list_code_standards(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/codes/standards")
    assert response.status_code == 200
    body = response.json()
    plugin_ids = {item["plugin_id"] for item in body}
    assert "IBC-2024" in plugin_ids
    assert "AISC360-22" in plugin_ids


def test_api_get_code_defaults(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/codes/defaults")
    assert response.status_code == 200
    body = response.json()
    assert body["jurisdiction"] == "US"
    assert body["configuration"]["governing_building_code"]["edition"] == "IBC 2024"


def test_api_validate_code_configuration(api_client: TestClient) -> None:
    defaults = api_client.get("/api/v1/codes/defaults").json()
    response = api_client.post(
        "/api/v1/codes/validate",
        json={"configuration": defaults["configuration"]},
    )
    assert response.status_code == 200
    assert response.json()["is_valid"] is True
