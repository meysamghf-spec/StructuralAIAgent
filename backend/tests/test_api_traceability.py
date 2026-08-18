"""API tests — traceability endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_api_create_link_and_get_graph(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Trace API Project"}).json()
    project_id = project["project"]["id"]
    source_id = str(uuid4())
    target_id = str(uuid4())

    create_response = api_client.post(
        "/api/v1/traceability/links",
        json={
            "project_id": project_id,
            "source_type": "requirement",
            "source_id": source_id,
            "target_type": "file",
            "target_id": target_id,
            "relationship_type": "REQUIREMENT_TO_SOURCE",
        },
    )
    assert create_response.status_code == 201

    graph_response = api_client.get(
        "/api/v1/traceability/graph",
        params={"project_id": project_id},
    )
    assert graph_response.status_code == 200
    assert len(graph_response.json()["links"]) == 1


def test_api_target_lineage(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Lineage API Project"}).json()
    project_id = project["project"]["id"]
    file_id = str(uuid4())
    memory_id = str(uuid4())

    api_client.post(
        "/api/v1/traceability/links",
        json={
            "project_id": project_id,
            "source_type": "file",
            "source_id": file_id,
            "target_type": "memory",
            "target_id": memory_id,
            "relationship_type": "SOURCE_TO_MEMORY",
        },
    )

    lineage_response = api_client.get(
        "/api/v1/traceability/target",
        params={
            "project_id": project_id,
            "object_type": "memory",
            "object_id": memory_id,
        },
    )
    assert lineage_response.status_code == 200
    assert len(lineage_response.json()["links"]) == 1


def test_api_source_lineage(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Impact API Project"}).json()
    project_id = project["project"]["id"]
    analysis_id = str(uuid4())
    design_id = str(uuid4())

    api_client.post(
        "/api/v1/traceability/links",
        json={
            "project_id": project_id,
            "source_type": "analysis_result",
            "source_id": analysis_id,
            "target_type": "design_result",
            "target_id": design_id,
            "relationship_type": "ANALYSIS_TO_DESIGN",
        },
    )

    impact_response = api_client.get(
        "/api/v1/traceability/impact",
        params={
            "project_id": project_id,
            "object_type": "analysis_result",
            "object_id": analysis_id,
        },
    )
    assert impact_response.status_code == 200
    assert impact_response.json()["links"][0]["relationship_type"] == "ANALYSIS_TO_DESIGN"
