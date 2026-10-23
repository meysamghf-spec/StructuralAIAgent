"""Collect engineering runs produced in chat for one project (analysis, beam, optimization, AutoCAD, exports).

Chat results live in conversation message metadata; this view makes them visible on Results/CAD/
Optimization/Validation/Traceability pages and works retroactively for older chats (no backfill job needed).
"""
from __future__ import annotations

from typing import Any

_LABELS = {
    "frame3d_analysis": "3D frame analysis",
    "aci_rc_beam": "RC beam check",
    "demo_rc_beam": "Beam calculation",
    "frame_optimization": "Frame optimization",
}


def _summary(eng: dict[str, Any]) -> dict[str, Any]:
    res = eng.get("results") if isinstance(eng.get("results"), dict) else {}
    out: dict[str, Any] = {}
    for k in ("max_drift_ratio", "period_s", "base_shear_kn", "total_weight_kn", "max_moment_knm", "max_shear_kn",
              "cost_before", "cost_after", "saving_pct", "utilization"):
        v = res.get(k) if k in res else eng.get(k)
        if isinstance(v, (int, float, str)):
            out[k] = v
    return out


def extract_runs(conversation, messages) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for m in messages:
        md = m.metadata or {}
        role = getattr(m.role, "value", m.role)
        if role != "assistant" or not md:
            continue
        base = {"message_id": str(m.id), "conversation_id": str(conversation.id), "conversation_title": conversation.title,
                "created_at": m.created_at.isoformat()}
        eng = md.get("engineering_results")
        if isinstance(eng, dict) and eng.get("kind"):
            kind = str(eng["kind"])
            if md.get("intent") == "frame_optimization":
                kind = "frame_optimization"
            runs.append({**base, "kind": kind, "label": eng.get("label") or _LABELS.get(kind, kind.replace("_", " ")),
                         "status": str(eng.get("status") or md.get("execution_status") or "completed"),
                         "inputs": eng.get("inputs") if kind == "frame3d_analysis" else (eng.get("frame") if kind == "frame_optimization" else None),
                         **({"optimization": {k: eng.get(k) for k in ("initial", "fsd", "optimal", "groups", "savings_pct")}}
                            if kind == "frame_optimization" else {}),
                         "summary": _summary(eng), "validation": md.get("validation_status")})
        ac = md.get("autocad_result")
        if isinstance(ac, dict) and ac.get("job_id"):
            runs.append({**base, "kind": "autocad", "label": ac.get("title") or "AutoCAD drawing",
                         "status": (ac.get("review") or {}).get("status", "ready"), "job_id": ac.get("job_id"),
                         "filename": ac.get("filename"), "inputs": None, "summary": {}})
        if not eng and not ac and md.get("mode") == "agent_execution" and md.get("execution_id"):
            runs.append({**base, "kind": "agent_execution", "label": (md.get("engineering_task") or {}).get("objective")
                         if isinstance(md.get("engineering_task"), dict) else "Assistant run",
                         "status": str(md.get("execution_status") or "completed"), "inputs": None, "summary": {}})
    return runs
