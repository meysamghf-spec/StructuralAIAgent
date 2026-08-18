"""API integration tests — project isolation."""

from fastapi.testclient import TestClient


def test_pem_update_does_not_affect_other_project(api_client: TestClient) -> None:
    project_a = api_client.post("/api/v1/projects", json={"name": "Project A"}).json()
    project_b = api_client.post("/api/v1/projects", json={"name": "Project B"}).json()

    pem_a = api_client.get(
        f"/api/v1/projects/{project_a['project']['id']}/pem/current"
    ).json()["pem"]
    pem_a["metadata"]["name"] = "Mutated A"
    api_client.put(
        f"/api/v1/projects/{project_a['project']['id']}/pem",
        json={"pem": pem_a, "change_type": "PEM_UPDATE", "summary": "mutate A"},
    )

    pem_b = api_client.get(
        f"/api/v1/projects/{project_b['project']['id']}/pem/current"
    ).json()["pem"]
    assert pem_b["metadata"]["name"] == "Project B"
