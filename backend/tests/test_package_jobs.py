"""Background ZIP jobs: progress, caching, failure reporting, owner isolation."""
import time

import pytest

from app.application import package_jobs as pj
from app.application import results_package as rp

INP = {"storeys": 2, "bays_x": 2, "bays_y": 1}


@pytest.fixture(autouse=True)
def _root(tmp_path, monkeypatch):
    monkeypatch.setattr(pj, "ROOT", tmp_path)


def _wait(job_id, owner="u1", timeout=10):
    t = time.time()
    while time.time() - t < timeout:
        st = pj.status(job_id, owner)
        if st["state"] != "running":
            return st
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_job_builds_then_cache_hit(monkeypatch):
    calls = []
    monkeypatch.setattr(rp, "build_zip", lambda i, o, on_file=None: (calls.append(1) or (b"PK-zip", ["a.xlsx", "b.csv"])))
    st = _wait(pj.start(INP, None, owner="u1")["job_id"])
    assert st["state"] == "done" and st["files"] == 2 and pj.zip_path(st["job_id"], "u1").read_bytes() == b"PK-zip"
    again = pj.start(INP, None, owner="u1")
    assert again["state"] == "done" and again.get("cached") and len(calls) == 1


def test_failure_is_reported(monkeypatch):
    def boom(i, o, on_file=None):
        raise RuntimeError("renderer crashed")

    monkeypatch.setattr(rp, "build_zip", boom)
    st = _wait(pj.start({"storeys": 9}, None, owner="u1")["job_id"])
    assert st["state"] == "failed" and "renderer crashed" in st["error"]
    with pytest.raises(KeyError):
        pj.zip_path(st["job_id"], "u1")


def test_owner_isolation_and_bad_ids(monkeypatch):
    monkeypatch.setattr(rp, "build_zip", lambda i, o, on_file=None: (b"x", ["a"]))
    jid = pj.start({"storeys": 3}, None, owner="u1")["job_id"]
    _wait(jid)
    with pytest.raises(KeyError):
        pj.status(jid, "someone-else")
    with pytest.raises(KeyError):
        pj.status("../etc/passwd")
