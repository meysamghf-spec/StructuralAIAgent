from fastapi.testclient import TestClient


def test_new_project_with_iranian_default_profile_validates_cleanly(api_client: TestClient) -> None:
    pid = api_client.post("/api/v1/projects", json={"name": "Iran default"}).json()["project"]["id"]
    report = api_client.post(f"/api/v1/projects/{pid}/validate").json()
    codes = [f["code"] for f in report["findings"]]
    assert "CODE_EDITION_MISMATCH" not in codes  # Mabhas 6 vs Standard 2800 are different standards
    assert "CODE_SOFTWARE_DEFAULT" not in codes  # the Iranian national set is the adopted profile
    assert report["overall_status"] == "PASS"
