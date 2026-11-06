"""Find the frame a project already has from its *whole* chat history, or assume the documented defaults.

Order (first hit wins):
  1. the newest usable 3D-frame run of any chat in the project (Model page / chat analysis);
  2. the newest chat-optimization run of the project (its frame);
  3. frame descriptions written in any of the project's chats (user messages, newest first, merged field by field);
  4. nothing at all → the default frame (4 storeys, 3×3 bays of 5 m, h=3.2 m, zone high / Arak, soil II, Mabhas 9).
Missing pieces in 2-3 are filled with the same defaults; every assumption is returned in Persian and English so
the user never has to type «assume defaults».
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.frame3d_followup import DEFAULTS

GEOMETRY = ("storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m", "storey_height_m")
# Every form field the project's own chats/runs may supply (geometry, sections, materials, loads, seismic data).
_PREFILL_KEYS = GEOMETRY + ("column_b_m", "column_h_m", "beam_b_m", "beam_h_m", "slab_t_m", "fc_mpa", "fy_mpa",
                            "dead_kn_m2", "live_kn_m2", "roof_live_kn_m2", "wall_kn_m", "zone", "soil", "importance",
                            "system", "allowable_bearing_kpa")
_FA_DIGITS = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")

LABELS = {
    "frame": {"en": "3D frame from chat / Model page", "fa": "قاب سه‌بعدی از چت / صفحه مدل"},
    "optimization": {"en": "Frame from an earlier chat optimization", "fa": "قاب بهینه‌سازی قبلی در چت"},
    "chat_text": {"en": "Frame described in the project's chats", "fa": "قاب توصیف‌شده در چت‌های پروژه"},
    "default": {"en": "Default frame (no model in the project yet)", "fa": "قاب پیش‌فرض (پروژه هنوز مدلی ندارد)"},
}
_KEY_FA = {"storeys": "تعداد طبقات", "bays_x": "تعداد دهانه X", "bays_y": "تعداد دهانه Y", "bay_x_m": "طول دهانه X (متر)",
           "bay_y_m": "طول دهانه Y (متر)", "storey_height_m": "ارتفاع طبقه (متر)"}


def _fa(v: Any) -> str:
    return f"{v:g}".translate(_FA_DIGITS) if isinstance(v, float) else str(v).translate(_FA_DIGITS)


def default_assumptions_fa() -> list[str]:
    d = DEFAULTS
    return [
        f"{_fa(d['storeys'])} طبقه، {_fa(d['bays_x'])}×{_fa(d['bays_y'])} دهانه {_fa(float(d['bay_x_m']))} متری، "
        f"ارتفاع طبقه {_fa(float(d['storey_height_m']))} متر",
        "قاب خمشی بتن‌آرمه متوسط؛ ستون ۵۰×۵۰ و تیر ۴۰×۵۰ سانتی‌متر به‌عنوان نقطه شروع",
        "استاندارد ۲۸۰۰ (ویرایش ۴): پهنه با خطر نسبی زیاد (اراک، A=۰٫۳۰)، خاک نوع II، اهمیت I=۱",
        "بارها و ترکیب‌بارها طبق مبحث ۶؛ طراحی و کنترل‌ها طبق مبحث ۹",
        "مقاطع: کاتالوگ استاندارد با گام ۵ سانتی‌متر",
    ]


def _project_runs(conv, account, project_id: str) -> list[dict[str, Any]]:
    try:
        return list(conv.list_project_chat_runs(account, UUID(project_id)))
    except Exception:  # noqa: BLE001 — best effort
        return []


def _project_user_texts(conv, account, project_id: str, limit: int = 400) -> list[str]:
    """User messages of every chat in the project, newest first."""
    return [t for t, _, _ in _project_user_texts_titled(conv, account, project_id, limit)]


def _project_user_texts_titled(conv, account, project_id: str, limit: int = 400) -> list[tuple[str, str, str]]:
    """(text, chat title, created_at) of every user message in the project's chats, newest first."""
    out: list[tuple[str, str, str]] = []
    try:
        convs = conv.list_conversations(account, project_id=UUID(project_id), limit=200)
    except Exception:  # noqa: BLE001
        return []
    for c in convs:
        if getattr(c, "project_id", None) is not None and str(c.project_id) != str(project_id):
            continue  # strict project isolation
        try:
            msgs = conv.list_messages(c.id, account)
        except Exception:  # noqa: BLE001
            continue
        for m in msgs:
            if str(getattr(m.role, "value", m.role)).lower() == "user" and (m.content or "").strip():
                out.append((str(getattr(m, "created_at", "")), m.content, str(getattr(c, "title", "") or "")))
    out.sort(key=lambda t: t[0], reverse=True)
    return [(t, title, created_at) for created_at, t, title in out[:limit]]


def inputs_from_texts(texts: list[str]) -> dict[str, Any] | None:
    """Merge frame descriptions from chat texts (newest first: a newer value wins, older ones fill the gaps)."""
    from app.application import frame3d_chat_analysis as f3

    merged: dict[str, Any] = {}
    for t in texts:
        try:
            if not f3.is_frame3d_request(t):
                continue
            inp = f3.parse_frame3d_request(t)
        except Exception:  # noqa: BLE001
            continue
        for k in inp.parsed:
            v = getattr(inp, k, None)
            if v is not None and k not in merged:
                merged[k] = v
        if not merged.get("lang"):
            merged["lang"] = "fa" if any("\u0600" <= ch <= "\u06ff" for ch in t) else "en"
    return merged if any(merged.get(k) is not None for k in ("storeys", "bays_x", "bays_y")) else None


def _fill(inputs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    out = dict(inputs)
    assumed = []
    for k in GEOMETRY:
        if out.get(k) is None:
            out[k] = DEFAULTS[k]
            assumed.append(k)
    return out, assumed


def resolve_project_frame(conv, account, project_id: str | None, *, include_default: bool = True) -> dict[str, Any] | None:
    """Resolve a project's current frame; newer explicit chat specifications supersede older saved runs."""
    from app.application.chat_runs import pick_usable_frame_run

    found: tuple[str, dict[str, Any]] | None = None
    chat_title: str | None = None
    found_at = ""
    titled: list[tuple[str, str, str]] = []
    chat_updated_keys: list[str] = []
    if project_id and conv is not None:
        runs = _project_runs(conv, account, project_id)
        titled = _project_user_texts_titled(conv, account, project_id)
        run = pick_usable_frame_run(runs)
        if run:
            found = ("frame", dict(run["inputs"]))
            chat_title = run.get("conversation_title")
            found_at = str(run.get("created_at") or "")
        if found is None:
            for r in sorted(runs, key=lambda r: str(r.get("created_at") or ""), reverse=True):
                ins = r.get("inputs")
                if r.get("kind") in ("frame_optimization", "frame3d_analysis") and isinstance(ins, dict) and any(
                    ins.get(k) is not None for k in ("storeys", "bays_x", "bays_y")
                ):
                    found = ("optimization" if r.get("kind") == "frame_optimization" else "frame", dict(ins))
                    chat_title = r.get("conversation_title")
                    found_at = str(r.get("created_at") or "")
                    break
        if found is None:
            ins = inputs_from_texts([t for t, _, _ in titled])
            if ins:
                found = ("chat_text", ins)
                chat_title = next((title for t, title, _ in titled if inputs_from_texts([t])), None)
                chat_updated_keys = list(ins)
    if found is None:
        if not include_default:
            return None
        inputs, assumed = _fill({"lang": "fa", "zone": "HIGH", "soil": "II", "seismic_code": "IRAN_2800"})
        return {"source": "default", "inputs": inputs, "assumed": assumed, "assumptions_fa": default_assumptions_fa(),
                "label": LABELS["default"], "chat_title": None, "chat_updated_keys": []}

    source, raw = found
    if source != "chat_text" and project_id and conv is not None:
        # Older chat text may fill gaps, but a newer explicit project-chat specification supersedes an older run.
        all_chat = inputs_from_texts([t for t, _, _ in titled]) or {}
        raw = {**raw, **{k: all_chat[k] for k in GEOMETRY if raw.get(k) is None and all_chat.get(k) is not None}}
        newer_texts = [t for t, _, created_at in titled if created_at and created_at > found_at]
        newer_chat = inputs_from_texts(newer_texts) or {}
        if newer_chat:
            geometry_restart = any(k in newer_chat for k in GEOMETRY)
            if geometry_restart:
                # A new geometry request starts a new model definition; do not silently carry old spans/heights.
                raw = {k: v for k, v in raw.items() if k not in GEOMETRY}
            raw.update(newer_chat)
            chat_updated_keys = list(newer_chat)
            if geometry_restart:
                # Include newly assumed geometry too, so stale browser values are replaced by explicit defaults.
                chat_updated_keys = list(dict.fromkeys([*chat_updated_keys, *GEOMETRY]))
            chat_title = next((title for t, title, created_at in titled
                               if created_at and created_at > found_at and inputs_from_texts([t])), chat_title)

    inputs, assumed = _fill(raw)
    notes = [f"{_KEY_FA[k]}: {_fa(float(inputs[k]) if isinstance(inputs[k], float) else inputs[k])} (پیش‌فرض)" for k in assumed]
    found_keys = [k for k, v in raw.items() if v is not None and k in _PREFILL_KEYS]
    return {"source": source, "inputs": inputs, "assumed": assumed, "assumptions_fa": notes, "label": LABELS[source],
            "chat_title": chat_title or None, "found_keys": found_keys, "chat_updated_keys": chat_updated_keys}
