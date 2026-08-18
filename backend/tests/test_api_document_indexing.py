"""API integration tests — document indexing endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(api_client: TestClient, name: str = "Doc Index Project") -> str:
    response = api_client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def _upload_file(api_client: TestClient, project_id: str, content: bytes = b"a\nb\nc") -> str:
    response = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("spec.txt", content, "text/plain")},
        headers={"X-Actor-Id": "file-uploader"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_api_index_file_and_retrieve_memories(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    file_id = _upload_file(api_client, project_id)

    index_response = api_client.post(
        f"/api/v1/projects/{project_id}/files/{file_id}/index",
        headers={"X-Actor-Id": "indexer"},
    )
    assert index_response.status_code == 201
    body = index_response.json()
    assert body["memory_type"] == "EXTRACTED_INFORMATION"
    assert body["source_type"] == "file"
    assert body["source_id"] == file_id
    assert body["created_by"] == "indexer"

    file_memories = api_client.get(
        f"/api/v1/projects/{project_id}/files/{file_id}/memory",
    )
    assert file_memories.status_code == 200
    assert len(file_memories.json()["memories"]) == 1

    filtered = api_client.get(
        f"/api/v1/projects/{project_id}/memory",
        params={"source_type": "file", "source_id": file_id},
    )
    assert filtered.status_code == 200
    assert len(filtered.json()["memories"]) == 1


def test_api_file_memory_isolation(api_client: TestClient) -> None:
    project_a = _create_project(api_client, "Doc Iso A")
    project_b = _create_project(api_client, "Doc Iso B")
    file_id = _upload_file(api_client, project_a)

    api_client.post(f"/api/v1/projects/{project_a}/files/{file_id}/index")

    assert api_client.get(
        f"/api/v1/projects/{project_b}/files/{file_id}/memory",
    ).status_code == 404

    assert (
        api_client.get(
            f"/api/v1/projects/{project_b}/memory",
            params={"source_type": "file", "source_id": file_id},
        ).json()["memories"]
        == []
    )


def test_api_index_unknown_file_404(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    missing_file = uuid4()

    response = api_client.post(
        f"/api/v1/projects/{project_id}/files/{missing_file}/index",
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_FILE_NOT_FOUND"
