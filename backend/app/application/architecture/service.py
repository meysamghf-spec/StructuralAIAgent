"""Architectural set storage (file storage/arch_sets/<id>/) and the chat interview."""
from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.infrastructure.config import get_settings

from . import program as prog
from .program import BuildingProgram

_SAFE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _root() -> Path:
    p = get_settings().resolved_file_storage_root / "arch_sets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_set(p: BuildingProgram, *, owner: str, project_id: str | None, source: str = "") -> dict[str, Any]:
    from app.application import drawing_standard as ds
    from .build import write_set

    sid = uuid.uuid4().hex
    d = _root() / sid
    info = ds.TitleInfo(project=p.project_name, code="Mabhas 4 / municipal rules")
    meta = write_set(p, d, info)
    meta.update({"id": sid, "owner": owner, "project_id": project_id, "source": source[:500],
                 "created_at": datetime.now(UTC).isoformat(), "title": f"{p.floors}-storey, plot {p.plot_width_m:g}x{p.plot_depth_m:g} m"})
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def _load(sid: str) -> dict[str, Any] | None:
    if not _SAFE.match(sid):
        return None
    f = _root() / sid / "meta.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def get_set(sid: str, owner: str) -> dict[str, Any] | None:
    m = _load(sid)
    return m if m and m.get("owner") == owner else None


def file_path(sid: str, owner: str, name: str) -> Path | None:
    m = get_set(sid, owner)
    if not m or not _SAFE.match(name):
        return None
    f = _root() / sid / name
    return f if f.exists() else None


def list_sets(owner: str, project_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    out = []
    for f in _root().glob("*/meta.json"):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if m.get("owner") != owner or (project_id and m.get("project_id") != project_id):
            continue
        out.append(m)
    out.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return out[:limit]


def set_project_files(sid: str, files: dict[str, str]) -> None:
    f = _root() / sid / "meta.json"
    m = json.loads(f.read_text(encoding="utf-8"))
    m["project_files"] = files
    f.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ chat
_ARCH = re.compile(
    r"نقشه(?:‌|\s)*(?:ها|های)?(?:ی)?\s*معماری|architectural\s+(?:drawings?|set|plans?|drawing set)|"
    r"(?:نقشه|پلان|plans?|drawings?).{0,40}(?:ساختمان|building).{0,40}(?:طبقه|stor(?:e)?y|floors?)|"
    r"(?:ساختمان|building).{0,30}(?:\d|[۰-۹])+\s*(?:طبقه|stor(?:e)?y|floors?).{0,60}(?:زمین|plot|lot|بکش|draw|نقشه|plan)|"
    r"(?:زمین|plot|lot)\s*(?:\d|[۰-۹])+\s*(?:[x×*]|در|by)",
    re.I,
)
_DEFAULTS_OK = re.compile(r"^\s*(?:ok|okay|yes|go|default|defaults|بله|باشه|اوکی|پیش\s*فرض|پیش‌فرض|ادامه|همین|بکش|برو)\b", re.I)
REQUIRED = ("plot", "floors")


def wants_arch(text: str) -> bool:
    return bool(_ARCH.search(prog.normalize(text or "")))


def _fa(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def _defaults_lines(p: BuildingProgram, keys: list[str], fa: bool) -> list[str]:
    vals = {"plot": f"{p.plot_width_m:g}×{p.plot_depth_m:g} m", "street_side": ("شمالی (گذر در جنوب)" if fa else "north plot (street on the south)") if p.street_side == "south" else ("جنوبی" if fa else "south plot (street on the north)"),
            "street_width": f"{p.street_width_m:g} m", "floors": str(p.floors), "units": str(p.units_per_floor),
            "bedrooms": str(p.bedrooms), "parking": ("بله" if fa else "yes") if p.parking else ("خیر" if fa else "no"),
            "elevator": ("خودکار (از ۴ طبقه)" if fa else "auto (from 4 floors)"), "structure": ("بتنی" if fa else "concrete") if p.structure == "concrete" else ("فلزی" if fa else "steel"),
            "city": p.city}
    return [f"- {prog.QUESTIONS[k][0 if fa else 1]} — {'پیش‌فرض' if fa else 'default'}: **{vals.get(k, '')}**" for k in keys]


def chat_turn(text: str, *, owner: str, project_id: str | None, pending: dict[str, Any] | None,
              save_project_file: Callable[[str, bytes, str], str | None] | None) -> tuple[str, dict[str, Any]] | None:
    """Architect-style interview -> architectural set. `pending` is the last assistant's arch_interview metadata."""
    if pending is None and not wants_arch(text):
        return None
    fa = _fa(text) or bool(pending and pending.get("fa"))
    base = BuildingProgram.from_dict(pending["program"]) if pending else None
    got0 = set(pending.get("got", [])) if pending else set()
    p, got = prog.parse(text, base)
    if pending is not None and not got and not wants_arch(text) and not _DEFAULTS_OK.search(prog.normalize(text)):
        return None  # user moved on
    got |= got0
    accept = bool(pending) and bool(_DEFAULTS_OK.search(prog.normalize(text)))
    need = [k for k in REQUIRED if k not in got]
    if need and not accept:
        ask = need + [k for k in prog.missing(got) if k not in need]
        head = ("برای طراحی نقشه‌های معماری فقط این موارد را لازم دارم (بقیه با پیش‌فرض):" if fa
                else "To draw the architectural set I only need these (anything else uses the default):")
        lines = [head, ""] + _defaults_lines(p, need, fa) + [""]
        lines.append("سایر موارد (اگر تغییری لازم نیست بنویسید «پیش‌فرض»):" if fa else "Other items (reply \"defaults\" to keep them):")
        lines += _defaults_lines(p, [k for k in ask if k not in need], fa)
        return "\n".join(lines), {"mode": "rule_based", "intent": "architecture_interview",
                                  "arch_interview": {"program": p.to_dict(), "got": sorted(got), "fa": fa}}
    warns = prog.validate(p)
    m = create_set(p, owner=owner, project_id=project_id, source=text)
    saved: dict[str, str] = {}
    if save_project_file and project_id:
        d = _root() / m["id"]
        tag = m["id"][:6]
        for name in [s["dxf"] for s in m["sheets"]] + ([m["pdf"]] if m.get("pdf") else []):
            try:
                fid = save_project_file(f"arch-{tag}-{name}", (d / name).read_bytes(),
                                        "application/pdf" if name.endswith(".pdf") else "application/dxf")
                if fid:
                    saved[name] = fid
            except Exception:  # noqa: BLE001 - the set is still on the CAD page
                pass
        if saved:
            set_project_files(m["id"], saved)
    defaults = [k for k in prog.QUESTIONS if k not in got]
    lines = [("**نقشه‌های معماری آماده شد** — " if fa else "**Architectural set ready** — ") + m["title"], ""]
    lines.append(("شیت‌ها: " if fa else "Sheets: ") + ", ".join(f"{s['no']} {s['title_fa'] if fa else s['title_en']}" for s in m["sheets"]))
    bad = [c for c in m["checks"] if c[3] != "OK"]
    lines.append("")
    lines.append((f"کنترل ضوابط: {len(m['checks']) - len(bad)}/{len(m['checks'])} قبول" if fa else f"Rule checks: {len(m['checks']) - len(bad)}/{len(m['checks'])} pass")
                 + ("" if not bad else " — " + "; ".join(f"{c[0]}: {c[2]} ({c[1]})" for c in bad)))
    if defaults:
        lines.append(("پیش‌فرض‌های استفاده‌شده: " if fa else "Defaults used: ") + "; ".join(x[2:].split(" — ")[0] + " = " + x.split("**")[1] for x in _defaults_lines(p, defaults, fa)))
    for w in warns + m.get("warnings", []):
        lines.append(f"- ⚠ {w}")
    if saved:
        lines.append("")
        lines.append(f"{len(saved)} فایل در «فایل‌ها» و بخش CAD پروژه ذخیره شد." if fa else f"{len(saved)} files saved to the project Files and CAD section.")
    meta = {"mode": "rule_based", "intent": "architecture_set",
            "arch_set": {"id": m["id"], "title": m["title"], "sheets": m["sheets"], "pdf": m.get("pdf"), "zip": m.get("zip"),
                         "checks": m["checks"], "project_files": saved}}
    return "\n".join(lines), meta
