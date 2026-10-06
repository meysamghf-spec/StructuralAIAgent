"""API integration tests — project file endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(api_client: TestClient, name: str = "Files API Project") -> str:
    response = api_client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_api_upload_list_get_and_download(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    files = {"file": ("sample.txt", b"line one\nline two", "text/plain")}

    upload = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files=files,
        headers={"X-Actor-Id": "file-uploader"},
    )
    assert upload.status_code == 201
    body = upload.json()
    assert body["filename"] == "sample.txt"
    assert body["created_by"] == "file-uploader"
    assert body["parsing_status"] == "COMPLETE"
    assert body["extraction_status"] == "COMPLETE"
    file_id = body["id"]

    listed = api_client.get(f"/api/v1/projects/{project_id}/files")
    assert listed.status_code == 200
    assert len(listed.json()["files"]) == 1

    meta = api_client.get(f"/api/v1/projects/{project_id}/files/{file_id}")
    assert meta.status_code == 200
    assert meta.json()["filename"] == "sample.txt"

    content = api_client.get(f"/api/v1/projects/{project_id}/files/{file_id}/content")
    assert content.status_code == 200
    assert content.content == b"line one\nline two"


def test_api_project_isolation(api_client: TestClient) -> None:
    project_a = _create_project(api_client, "API Iso A")
    project_b = _create_project(api_client, "API Iso B")

    upload = api_client.post(
        f"/api/v1/projects/{project_a}/files",
        files={"file": ("iso.txt", b"secret", "text/plain")},
    )
    file_id = upload.json()["id"]

    assert api_client.get(f"/api/v1/projects/{project_b}/files").json()["files"] == []
    assert api_client.get(f"/api/v1/projects/{project_b}/files/{file_id}").status_code == 404
    assert (
        api_client.get(f"/api/v1/projects/{project_b}/files/{file_id}/content").status_code
        == 404
    )


def test_api_invalid_upload(api_client: TestClient) -> None:
    project_id = _create_project(api_client, "Invalid Upload Project")

    bad_extension = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("malware.exe", b"binary", "application/octet-stream")},
    )
    assert bad_extension.status_code == 400

    bad_name = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("../evil.txt", b"x", "text/plain")},
    )
    assert bad_name.status_code == 400


def test_api_unknown_project(api_client: TestClient) -> None:
    missing = uuid4()
    response = api_client.get(f"/api/v1/projects/{missing}/files")
    assert response.status_code == 404


def test_api_list_empty_project_files(api_client: TestClient) -> None:
    project_id = _create_project(api_client, "Empty Files Project")
    listed = api_client.get(f"/api/v1/projects/{project_id}/files")
    assert listed.status_code == 200
    body = listed.json()
    assert body["project_id"] == project_id
    assert body["files"] == []


def test_api_list_multiple_file_types_exposes_safe_metadata_only(api_client: TestClient) -> None:
    project_id = _create_project(api_client, "Typed Files Project")
    uploads = (
        ("notes.txt", b"load combinations", "text/plain"),
        ("plans.pdf", b"%PDF-1.4 sample", "application/pdf"),
        ("model.edb", b"etabs-model", "application/octet-stream"),
    )
    for filename, content, content_type in uploads:
        response = api_client.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": (filename, content, content_type)},
        )
        assert response.status_code == 201

    listed = api_client.get(f"/api/v1/projects/{project_id}/files")
    assert listed.status_code == 200
    files = listed.json()["files"]
    names = {item["filename"] for item in files}
    assert names == {"notes.txt", "plans.pdf", "model.edb"}
    serialized = listed.text
    assert "storage_path" not in serialized
    assert "C:\\" not in serialized
    assert "/var/" not in serialized
    for item in files:
        assert "id" in item
        assert item["project_id"] == project_id
        assert "filename" in item
        assert "file_type" in item
        assert "parsing_status" in item
        assert "extraction_status" in item
        assert "storage_path" not in item
        if item["filename"] == "model.edb":
            assert item["byte_length"] == len(b"etabs-model")
        assert "indexed" not in item


def test_api_list_files_requires_project_access(
    api_client: TestClient,
    monkeypatch,
) -> None:
    from app.infrastructure.config import get_settings

    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    get_settings.cache_clear()
    owner = {"X-Actor-Id": "file-tree-owner"}
    other = {"X-Actor-Id": "file-tree-other"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Private Files"},
        headers=owner,
    ).json()["project"]["id"]
    uploaded = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("secret.txt", b"owner-only", "text/plain")},
        headers=owner,
    )
    assert uploaded.status_code == 201
    file_id = uploaded.json()["id"]

    denied_list = api_client.get(f"/api/v1/projects/{project_id}/files", headers=other)
    assert denied_list.status_code == 403
    denied_get = api_client.get(f"/api/v1/projects/{project_id}/files/{file_id}", headers=other)
    assert denied_get.status_code == 403
    denied_download = api_client.get(
        f"/api/v1/projects/{project_id}/files/{file_id}/content",
        headers=other,
    )
    assert denied_download.status_code == 403

    allowed = api_client.get(f"/api/v1/projects/{project_id}/files", headers=owner)
    assert allowed.status_code == 200
    assert allowed.json()["files"][0]["filename"] == "secret.txt"
    monkeypatch.delenv("PROJECT_ACCESS_ENFORCED", raising=False)
    get_settings.cache_clear()


def test_api_upload_size_limit(api_client: TestClient, monkeypatch) -> None:
    from app.infrastructure.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_BYTES", "5")
    get_settings.cache_clear()

    project_id = _create_project(api_client, "API Size Limit")
    response = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("big.txt", b"123456", "text/plain")},
    )
    assert response.status_code == 413
