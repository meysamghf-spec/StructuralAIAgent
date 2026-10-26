"""Background "Download all (ZIP)" jobs.

Building the full results package takes 30-120 s (DXF -> PDF rendering dominates), which is too long for one
blocking browser request (proxy timeouts, backend restarts, no progress). The ZIP is built in a thread; job state
lives on disk under /tmp so every uvicorn worker can answer status polls, and finished ZIPs are cached by input
hash so a retry or a second click is instant.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

ROOT = Path(os.environ.get("SA_PACKAGE_DIR", "/tmp/sa-zip"))
CACHE_TTL_S = 6 * 3600
STALE_RUNNING_S = 15 * 60


def _code_stamp() -> str:
    from app.application import csi_text_export, results_package

    return "|".join(str(int(os.path.getmtime(m.__file__ or ""))) for m in (results_package, csi_text_export))


def cache_key(inputs: dict[str, Any], optimization: dict[str, Any] | None) -> str:
    raw = json.dumps({"i": inputs, "o": optimization, "v": _code_stamp()}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _write(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _job_dir(job_id: str) -> Path:
    if not job_id or any(c not in "0123456789abcdef" for c in job_id):
        raise KeyError(job_id)
    return ROOT / "jobs" / job_id


def status(job_id: str, owner: str | None = None) -> dict[str, Any]:
    d = _job_dir(job_id)
    try:
        st = json.loads((d / "status.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KeyError(job_id) from exc
    if owner is not None and st.get("owner", "") != owner:
        raise KeyError(job_id)
    if st.get("state") == "running" and time.time() - float(st.get("heartbeat", st.get("started", 0))) > STALE_RUNNING_S:
        st.update(state="failed", error="The ZIP job stopped (server restarted). Please try again.")
    st["elapsed_s"] = round((st.get("finished") or time.time()) - st.get("started", time.time()), 1)
    return st


def zip_path(job_id: str, owner: str | None = None) -> Path:
    st = status(job_id, owner)
    if st.get("state") != "done":
        raise KeyError(job_id)
    p = ROOT / "cache" / f"{st['key']}.zip"
    if not p.exists():
        raise KeyError(job_id)
    return p


def _cleanup() -> None:
    now = time.time()
    for sub in ("cache", "jobs"):
        base = ROOT / sub
        if not base.exists():
            continue
        for p in base.iterdir():
            try:
                if now - p.stat().st_mtime > CACHE_TTL_S:
                    if p.is_dir():
                        for f in p.iterdir():
                            f.unlink(missing_ok=True)
                        p.rmdir()
                    else:
                        p.unlink(missing_ok=True)
            except OSError:
                pass


def start(
    inputs: dict[str, Any],
    optimization: dict[str, Any] | None,
    *,
    owner: str = "",
    on_file: Callable[[str, bytes], str] | None = None,
) -> dict[str, Any]:
    """Start (or reuse) a package build; returns the job status."""
    (ROOT / "cache").mkdir(parents=True, exist_ok=True)
    (ROOT / "jobs").mkdir(parents=True, exist_ok=True)
    _cleanup()
    key = cache_key(inputs, optimization)
    job_id = uuid.uuid4().hex
    d = _job_dir(job_id)
    d.mkdir(parents=True)
    st: dict[str, Any] = {"job_id": job_id, "key": key, "state": "running", "started": time.time(), "owner": owner,
                          "heartbeat": time.time(), "files": 0, "file_ids": [], "error": None}
    cached = ROOT / "cache" / f"{key}.zip"
    meta = ROOT / "cache" / f"{key}.json"
    if cached.exists() and meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        st.update(state="done", finished=time.time(), files=m.get("files", 0), cached=True, size=cached.stat().st_size)
        if on_file:  # still honour "also save to project Files"
            threading.Thread(target=lambda: on_file("frame-results.zip", cached.read_bytes()), daemon=True).start()
        _write(d / "status.json", st)
        return status(job_id)
    _write(d / "status.json", st)

    def work() -> None:
        from app.application import results_package as rp

        stop = threading.Event()

        def beat() -> None:
            while not stop.wait(10):
                try:
                    cur = json.loads((d / "status.json").read_text(encoding="utf-8"))
                    cur["heartbeat"] = time.time()
                    _write(d / "status.json", cur)
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=beat, daemon=True).start()
        ids: list[str] = []
        try:
            saver = (lambda n, b: ids.append(on_file(n, b))) if on_file else None
            data, names = rp.build_zip(inputs, optimization, on_file=saver)
            tmp = cached.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(cached)
            _write(meta, {"files": len(names)})
            st.update(state="done", files=len(names), file_ids=[x for x in ids if x], size=len(data))
        except Exception as exc:  # noqa: BLE001 — reported to the browser as a clear error
            st.update(state="failed", error=f"Cannot build the package: {exc}")
        finally:
            stop.set()
            st["finished"] = time.time()
            st["heartbeat"] = time.time()
            _write(d / "status.json", st)

    threading.Thread(target=work, daemon=True, name=f"zip-{job_id[:8]}").start()
    return status(job_id)
