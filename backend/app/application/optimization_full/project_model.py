"""Detect the structural model a project already has outside the PEM: a chat / Model-page 3D frame or an imported
(ETABS/SAP/DXF) model.  Used by the Optimization page readiness and the 'Start optimization' form."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

STATE_SUFFIX = ".saia-import.json"


def frame_member_count(inputs: dict[str, Any]) -> int:
    try:
        s, bx, by = int(inputs["storeys"]), int(inputs["bays_x"]), int(inputs["bays_y"])
    except (KeyError, TypeError, ValueError):
        return 0
    cols = (bx + 1) * (by + 1)
    beams = bx * (by + 1) + by * (bx + 1)
    return max(s, 0) * (cols + beams)


def _latest_import(project_id: str, registry, files) -> dict[str, Any] | None:
    try:
        recs = [r for r in registry.list_project_files(UUID(project_id)) if r.filename.endswith(STATE_SUFFIX)]
        if not recs:
            return None
        rec = max(recs, key=lambda r: r.created_at)
        _, content = files.get_file_content(UUID(project_id), rec.id)
        return json.loads(content.decode("utf-8"))
    except Exception:  # noqa: BLE001 — detection is best effort, never breaks readiness
        return None


def detect_project_model(project_id: str | None, account, conv=None, registry=None, files=None) -> dict[str, Any] | None:
    """{'source': 'model'|'frame', 'member_count', 'load_combination_count', 'section_count', 'label'} or None."""
    if not project_id:
        return None
    if registry is not None and files is not None:
        st = _latest_import(project_id, registry, files)
        model = (st or {}).get("model") or {}
        counts = model.get("counts") or {}
        members = int(counts.get("members") or len(model.get("members") or []))
        if members > 0:
            return {"source": "model", "member_count": members,
                    "load_case_count": int(counts.get("load_patterns") or 0),
                    "load_combination_count": int(counts.get("combos") or 0),
                    "section_count": int(counts.get("sections") or 0),
                    "label": {"en": "Imported model", "fa": "مدل واردشده (ETABS/SAP/DXF)"}}
    if conv is not None:
        try:
            from app.api.routes.autocad import latest_frame_inputs

            inputs = latest_frame_inputs(conv, account, project_id)
        except Exception:  # noqa: BLE001
            inputs = None
        members = frame_member_count(inputs or {})
        if members > 0:
            return {"source": "frame", "member_count": members, "load_case_count": 0, "load_combination_count": 0,
                    "section_count": 0, "storeys": inputs.get("storeys"), "bays_x": inputs.get("bays_x"),
                    "bays_y": inputs.get("bays_y"),
                    "label": {"en": "3D frame from chat / Model page", "fa": "قاب سه‌بعدی از چت / صفحه مدل"}}
    return None
