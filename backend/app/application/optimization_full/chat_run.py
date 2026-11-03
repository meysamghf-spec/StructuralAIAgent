"""Run the full section optimizer (optimization_full) for a chat turn such as «بهینه کن».

Model resolution (first hit wins): the frame described in the message itself, the frame from the current chat,
the project's imported ETABS/SAP model, any frame in the project's chats, else the documented default frame.
Every assumption is reported back (Persian) so the chat card can list it.  Deterministic, no LLM.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CHAT_TIME_BUDGET_S = 25.0


def _frame_model(inputs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    from app.application import frame3d_chat_analysis as f3
    from app.application import frame3d_followup as fu
    from app.application.optimization_full.builder import model_from_frame

    inp = f3.inputs_from_dict({"seismic_code": "IRAN_2800", **inputs})
    assumed: list[str] = []
    if f3.missing_inputs(inp):
        assumed = fu.apply_defaults(inp)
    if f3.missing_inputs(inp):
        raise ValueError("frame inputs incomplete")
    if inp.storeys > f3.MAX_STOREYS or max(inp.bays_x, inp.bays_y) > f3.MAX_BAYS:
        raise ValueError("frame too large for chat optimization")
    return model_from_frame(inp), [f"{k} (پیش‌فرض)" for k in assumed]


def resolve_chat_model(text: str, prior_inputs: dict[str, Any] | None, conv=None, account=None,
                       project_id: str | None = None, registry=None, files=None) -> dict[str, Any]:
    """{'source', 'label_fa', 'model', 'assumed'}"""
    from app.application import frame3d_chat_analysis as f3
    from app.application.optimization_full.model_resolver import resolve_project_frame

    if f3.is_frame3d_request(text):
        inp = f3.parse_frame3d_request(text)
        raw = {k: getattr(inp, k) for k in inp.parsed if getattr(inp, k, None) is not None}
        if any(raw.get(k) for k in ("storeys", "bays_x", "bays_y")):
            model, assumed = _frame_model(raw)
            return {"source": "message", "label_fa": "قاب توصیف‌شده در همین پیام", "model": model, "assumed": assumed}
    if prior_inputs:
        model, assumed = _frame_model(dict(prior_inputs))
        return {"source": "frame", "label_fa": "قاب همین گفتگو", "model": model, "assumed": assumed}
    if project_id and registry is not None and files is not None:
        from app.application.optimization_full.project_model import _latest_import

        st = _latest_import(project_id, registry, files) or {}
        imported = st.get("model") or {}
        if imported.get("members"):
            from app.application.optimization_full.engine import prepare_model

            try:
                prepare_model(dict(imported))
                return {"source": "model", "label_fa": "مدل واردشده (ETABS/SAP/DXF)", "model": dict(imported), "assumed": []}
            except Exception:  # noqa: BLE001 — fall back to the chat frame
                logger.info("imported model not optimizable from chat; using frame")
    res = resolve_project_frame(conv, account, project_id)
    model, assumed = _frame_model(res["inputs"])
    return {"source": res["source"], "label_fa": res["label"]["fa"], "model": model,
            "assumed": [*res["assumptions_fa"], *assumed]}


def run_chat_optimization(text: str, prior_inputs: dict[str, Any] | None = None, *, conv=None, account=None,
                          project_id: str | None = None, registry=None, files=None,
                          time_budget_s: float = CHAT_TIME_BUDGET_S) -> dict[str, Any]:
    """Payload stored under engineering_results['optimization_full'] and rendered inline in the chat."""
    from app.application.optimization_full.engine import friendly_error, optimize_model
    from app.application.optimization_full.sections import merge_lists, parse_section_lists

    try:
        found = resolve_chat_model(text, prior_inputs, conv, account, project_id, registry, files)
        lists = merge_lists(parse_section_lists(text))
        res = optimize_model(found["model"], lists, {"time_budget_s": time_budget_s})
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat optimization_full failed")
        msg = friendly_error(exc) if not isinstance(exc, ValueError) else str(exc)
        return {"kind": "optimization_full", "status": "error", "error": msg, "result": None, "source_fa": None}
    res["assumed_inputs"] = [f"منبع مدل: {found['label_fa']}", *found["assumed"]]
    return {"kind": "optimization_full", "status": "done", "error": None, "result": res,
            "source": found["source"], "source_fa": found["label_fa"]}


def optimization_full_markdown(payload: dict[str, Any]) -> str:
    r = payload.get("result")
    if not r:
        return f"بهینه‌سازی کامل انجام نشد: {payload.get('error') or 'خطای نامشخص'}"
    ok = "طرح قابل‌قبول (همه کنترل‌ها برقرار)" if r.get("feasible") else "طرحی که همه کنترل‌ها را برقرار کند یافت نشد"
    return (f"**بهینه‌سازی کامل مقاطع** — {ok}. منبع مدل: {payload.get('source_fa')}. "
            f"هزینه: {round(float(r.get('cost') or 0)):,} {r.get('currency', '')}. جزئیات کامل در کارت زیر.")
