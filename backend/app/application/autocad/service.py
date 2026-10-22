"""Job storage + engineer review for AutoCAD v1 outputs (file-based)."""
from __future__ import annotations

import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.infrastructure.config import get_settings

from .preview import dxf_to_svg
from .standards import SHEET_REGISTRY

_ID = re.compile(r"^[0-9a-f]{32}$")


def _root() -> Path:
    p = get_settings().resolved_file_storage_root / "autocad_jobs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sheet_index() -> list[dict[str, Any]]:
    return [{"sheet_no": s.type.value, "title": s.title, "available": s.implemented} for s in SHEET_REGISTRY]


def save_job(doc, summary: dict[str, Any], *, kind: str, owner: str, source: str) -> dict[str, Any]:
    jid = uuid.uuid4().hex
    d = _root() / jid
    d.mkdir()
    buf = io.StringIO(); doc.write(buf)
    (d / "drawing.dxf").write_text(buf.getvalue(), encoding="utf-8")
    svg = dxf_to_svg(doc)
    (d / "preview.svg").write_text(svg, encoding="utf-8")
    meta = {"id": jid, "kind": kind, "owner": owner, "source": source[:300], "summary": summary,
            "layers": sorted({e.dxf.layer for e in doc.modelspace()}),
            "review": {"status": "pending" if kind == "vectorize" else "not_required", "note": "", "at": None},
            "created_at": datetime.now(timezone.utc).isoformat()}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return {**meta, "preview_svg": svg}


def job_dir(jid: str, owner: str) -> Path:
    if not _ID.match(jid):
        raise FileNotFoundError(jid)
    d = _root() / jid
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    if meta.get("owner") != owner:
        raise FileNotFoundError(jid)
    return d


def review(jid: str, owner: str, decision: str, note: str) -> dict[str, Any]:
    d = job_dir(jid, owner)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    meta["review"] = {"status": "accepted" if decision == "accept" else "flagged", "note": note[:1000],
                      "at": datetime.now(timezone.utc).isoformat()}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta
