"""Filesystem job store for long optimizations (works across uvicorn workers: state in JSON files, the job thread
runs in the worker that created it, cancel = flag file)."""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

ROOT = Path(os.environ.get("SAIA_OPT_JOBS_DIR") or "/tmp/saia_optimization_jobs")
MAX_RUNNING_PER_USER = 2


def _dir() -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    return ROOT


def _path(job_id: str) -> Path:
    if not job_id.isalnum():
        raise KeyError(job_id)
    return _dir() / f"{job_id}.json"


def _write(job_id: str, data: dict[str, Any]) -> None:
    p = _path(job_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, p)


def get(job_id: str) -> dict[str, Any] | None:
    try:
        return json.loads(_path(job_id).read_text(encoding="utf-8"))
    except (KeyError, FileNotFoundError, json.JSONDecodeError):
        return None


def running_for(owner: str) -> int:
    n = 0
    for p in _dir().glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d.get("owner") == owner and d.get("status") in ("queued", "running") and time.time() - d.get("updated", 0) < 120:
            n += 1
    return n


def cancel(job_id: str) -> bool:
    if get(job_id) is None:
        return False
    (_dir() / f"{job_id}.cancel").write_text("1")
    return True


def is_cancelled(job_id: str) -> bool:
    return (_dir() / f"{job_id}.cancel").exists()


def start(owner: str, meta: dict[str, Any], work: Callable[[Callable[[dict], None], Callable[[], bool]], dict[str, Any]]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:16]
    base = {"id": job_id, "owner": owner, "status": "queued", "progress": {"fraction": 0.0}, "meta": meta,
            "created": time.time(), "updated": time.time(), "result": None, "error": None}
    _write(job_id, base)
    state = dict(base)
    last = [0.0]

    def progress(p: dict[str, Any]) -> None:
        state.update(status="running", progress=p, updated=time.time())
        if time.time() - last[0] > 0.8:
            last[0] = time.time()
            _write(job_id, state)

    def runner() -> None:
        state.update(status="running", updated=time.time()); _write(job_id, state)
        try:
            res = work(progress, lambda: is_cancelled(job_id))
            state.update(status=res.get("status", "done"), result=res, progress={**state["progress"], "fraction": 1.0})
        except Exception as exc:  # noqa: BLE001
            state.update(status="error", error=str(exc)[:500], trace=traceback.format_exc()[-2000:])
        state["updated"] = time.time()
        _write(job_id, state)

    threading.Thread(target=runner, name=f"opt-{job_id}", daemon=True).start()
    return base


def public(job: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in job.items() if k not in ("owner", "trace")}
