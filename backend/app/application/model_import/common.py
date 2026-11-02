"""Shared neutral-model helpers, unit conversion and issue reporting for model import."""

from __future__ import annotations

import math
import shlex
from typing import Any

SUPPORTED_EXTENSIONS = (".e2k", ".s2k", ".f2k", ".dxf")
MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_NODES = 600

# force unit -> kN, length unit -> m
FORCE_TO_KN = {"N": 1e-3, "KN": 1.0, "KGF": 9.80665e-3, "KG": 9.80665e-3, "TONF": 9.80665, "TON": 9.80665,
               "LB": 4.4482216e-3, "KIP": 4.4482216}
LEN_TO_M = {"MM": 1e-3, "CM": 1e-2, "M": 1.0, "IN": 0.0254, "INCH": 0.0254, "FT": 0.3048}


class ImportError_(ValueError):
    """Raised when a file cannot be imported at all (wrong type, empty, .dwg...)."""

    def __init__(self, code: str, en: str, fa: str) -> None:
        self.code, self.en, self.fa = code, en, fa
        super().__init__(en)


def new_model(fmt: str, filename: str) -> dict[str, Any]:
    return {
        "format": fmt,
        "filename": filename,
        "units": {"force": "kN", "length": "m", "source": None},
        "nodes": {},          # id -> {x, y, z}
        "members": [],        # {id, i, j, type: beam|column|brace, section}
        "sections": {},       # name -> {shape, material, b, h, A, I22, I33, J, modifiers}
        "materials": {},      # name -> {E kN/m2, nu, unit_weight kN/m3, type}
        "supports": {},       # node -> [ux, uy, uz, rx, ry, rz]
        "load_patterns": {},  # name -> {type, self_weight}
        "member_loads": [],   # {member, pattern, w (kN/m, gravity +down)}
        "nodal_loads": [],    # {node, pattern, fx..mz}  (kN, kN.m, global)
        "combos": {},         # name -> {pattern: factor}
        "issues": [],         # {severity: blocking|approximated|ignored, code, item, en, fa}
        "assumptions": [],    # {en, fa}
        "counts": {},
    }


def issue(model: dict[str, Any], severity: str, code: str, item: str, en: str, fa: str) -> None:
    key = (severity, code, item)
    for it in model["issues"]:
        if (it["severity"], it["code"], it["item"]) == key:
            it["count"] = it.get("count", 1) + 1
            return
    model["issues"].append({"id": f"{code}:{item}", "severity": severity, "code": code, "item": item, "en": en, "fa": fa, "count": 1})


def assume(model: dict[str, Any], en: str, fa: str) -> None:
    if not any(a["en"] == en for a in model["assumptions"]):
        model["assumptions"].append({"en": en, "fa": fa})


def tokens(line: str) -> list[str]:
    try:
        return shlex.split(line, posix=True)
    except ValueError:
        return line.replace('"', " ").split()


def kv(toks: list[str], start: int = 0) -> dict[str, str]:
    """KEY VALUE pairs (e2k style) from position ``start``; keys upper-cased."""
    out: dict[str, str] = {}
    i = start
    while i < len(toks) - 1:
        out[toks[i].upper()] = toks[i + 1]
        i += 2
    return out


def eqpairs(line: str) -> dict[str, str]:
    """Key=Value pairs (CSI table style, s2k / f2k)."""
    out: dict[str, str] = {}
    for tok in tokens(line):
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def num(v: Any, default: float | None = None) -> float | None:
    try:
        f = float(str(v).replace("D", "E"))
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def rect_props(b: float, h: float) -> dict[str, float]:
    a, c = max(b, h), min(b, h)
    j = a * c**3 * (1 / 3 - 0.21 * (c / a) * (1 - c**4 / (12 * a**4))) if c > 0 else 0.0
    return {"A": b * h, "I33": b * h**3 / 12, "I22": h * b**3 / 12, "J": j}


def i_props(d: float, bf: float, tf: float, tw: float) -> dict[str, float]:
    hw = d - 2 * tf
    area = 2 * bf * tf + hw * tw
    i33 = (bf * d**3 - (bf - tw) * hw**3) / 12
    i22 = (2 * tf * bf**3 + hw * tw**3) / 12
    j = (2 * bf * tf**3 + hw * tw**3) / 3
    return {"A": area, "I33": i33, "I22": i22, "J": j}


def box_props(d: float, b: float, tf: float, tw: float) -> dict[str, float]:
    area = d * b - (d - 2 * tf) * (b - 2 * tw)
    i33 = (b * d**3 - (b - 2 * tw) * (d - 2 * tf) ** 3) / 12
    i22 = (d * b**3 - (d - 2 * tf) * (b - 2 * tw) ** 3) / 12
    j = 2 * tf * tw * (b - tw) ** 2 * (d - tf) ** 2 / (b * tw + d * tf - tw**2 - tf**2) if tf > 0 and tw > 0 else 0.0
    return {"A": area, "I33": i33, "I22": i22, "J": j}


def pipe_props(od: float, t: float) -> dict[str, float]:
    di = od - 2 * t
    area = math.pi * (od**2 - di**2) / 4
    i = math.pi * (od**4 - di**4) / 64
    return {"A": area, "I33": i, "I22": i, "J": 2 * i}


def finalize(model: dict[str, Any]) -> dict[str, Any]:
    """Cross-checks common to all formats; fills counts."""
    used = {m["section"] for m in model["members"]}
    for name in sorted(used):
        sec = model["sections"].get(name)
        if sec is None or not sec.get("A"):
            if any(i["item"] == name and i["severity"] == "blocking" for i in model["issues"]):
                continue
            issue(model, "blocking", "section_missing", name,
                  f"Section {name!r} has no readable properties - enter b/h or A, I33, I22 before analysis.",
                  f"مقطع «{name}» مشخصات قابل خواندن ندارد؛ قبل از تحلیل b/h یا A و I33 و I22 را وارد کنید.")
        elif sec.get("material") not in model["materials"]:
            issue(model, "approximated", "material_missing", name,
                  f"Section {name!r}: material not found - assumed concrete C25 (E = 23.5 GPa, 25 kN/m3).",
                  f"مقطع «{name}»: مصالح پیدا نشد؛ بتن C25 فرض شد (E = ۲۳٫۵ گیگاپاسکال، ۲۵ kN/m³).")
    if model["members"] and not model["supports"]:
        issue(model, "approximated", "no_supports", "model",
              "No supports found - nodes at the lowest level were assumed fixed.",
              "تکیه‌گاهی پیدا نشد؛ گره‌های پایین‌ترین تراز گیردار فرض شدند.")
        zmin = min(n["z"] for n in model["nodes"].values())
        for nid, n in model["nodes"].items():
            if abs(n["z"] - zmin) < 1e-6:
                model["supports"][nid] = [True] * 6
    if not model["members"]:
        issue(model, "blocking", "no_frames", "model",
              "No frame members (beams/columns/braces) were found, so SAIA's frame engine cannot analyse this file.",
              "هیچ عضو قابی (تیر/ستون/مهاربند) پیدا نشد؛ موتور قاب SAIA نمی‌تواند این فایل را تحلیل کند.")
    if len(model["nodes"]) > MAX_NODES:
        issue(model, "blocking", "too_large", "model",
              f"{len(model['nodes'])} nodes - above the {MAX_NODES}-node import limit of this phase.",
              f"{len(model['nodes'])} گره؛ بیش از سقف {MAX_NODES} گره در این مرحله.")
    if model["members"] and not model["member_loads"] and not model["nodal_loads"] and not any(
            p.get("self_weight") for p in model["load_patterns"].values()):
        issue(model, "approximated", "no_loads", "model",
              "No loads were read - only a Dead pattern with self-weight will be analysed unless you add loads.",
              "باری خوانده نشد؛ اگر بار اضافه نکنید فقط الگوی Dead با وزن خودی تحلیل می‌شود.")
        model["load_patterns"].setdefault("Dead", {"type": "Dead", "self_weight": 1.0})
    if model["members"] and not model["combos"]:
        pats = model["load_patterns"]
        dead = [p for p, v in pats.items() if str(v.get("type", "")).lower().startswith(("dead", "super"))]
        live = [p for p, v in pats.items() if str(v.get("type", "")).lower().startswith("live")]
        if dead:
            combo = {p: 1.2 for p in dead} | {p: 1.6 for p in live}
            model["combos"]["1.2D+1.6L (assumed)"] = combo
            assume(model, "No load combinations in the file: 1.2D + 1.6L assumed (Mabhas 6 / ASCE 7).",
                   "ترکیب باری در فایل نبود؛ 1.2D + 1.6L فرض شد (مبحث ۶ / ASCE 7).")
    model["counts"] = {
        "nodes": len(model["nodes"]), "members": len(model["members"]),
        "beams": sum(1 for m in model["members"] if m["type"] == "beam"),
        "columns": sum(1 for m in model["members"] if m["type"] == "column"),
        "braces": sum(1 for m in model["members"] if m["type"] == "brace"),
        "sections": len(used), "supports": len(model["supports"]),
        "load_patterns": len(model["load_patterns"]), "member_loads": len(model["member_loads"]),
        "nodal_loads": len(model["nodal_loads"]), "combos": len(model["combos"]),
    }
    return model


def parse_model_file(filename: str, data: bytes) -> dict[str, Any]:
    name = (filename or "").strip()
    low = name.lower()
    if low.endswith(".dwg"):
        raise ImportError_("dwg", "DWG is a closed binary format. In AutoCAD use Save As > DXF (any version) and upload the .dxf.",
                           "فرمت DWG بسته و باینری است. در AutoCAD از Save As گزینه‌ی DXF را انتخاب کنید و فایل .dxf را بارگذاری کنید.")
    ext = "." + low.rsplit(".", 1)[-1] if "." in low else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise ImportError_("ext", f"Unsupported file type {ext or '(none)'}; use .e2k, .s2k, .f2k or .dxf.",
                           f"نوع فایل {ext or '(بدون پسوند)'} پشتیبانی نمی‌شود؛ از .e2k، .s2k، .f2k یا .dxf استفاده کنید.")
    if not data:
        raise ImportError_("empty", "The file is empty.", "فایل خالی است.")
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportError_("size", "File larger than 20 MB.", "حجم فایل بیش از ۲۰ مگابایت است.")
    if ext != ".e2k":
        raise ImportError_("phase", f"{ext} import is not available yet - this phase imports ETABS .e2k only (SAP2000 .s2k, SAFE .f2k and DXF come next).",
                           f"ایمپورت {ext} هنوز فعال نیست؛ این مرحله فقط ETABS ‏.e2k را می‌خواند (SAP2000 ‏.s2k، SAFE ‏.f2k و DXF در مرحله‌ی بعد).")
    text = None
    for enc in ("utf-8-sig", "utf-16", "cp1256", "latin-1"):
        try:
            text = data.decode(enc)
            if "\x00" not in text:
                break
        except UnicodeDecodeError:
            continue
    text = text or data.decode("latin-1", errors="replace")
    from app.application.model_import.e2k_import import parse_e2k
    return finalize(parse_e2k(name, text))
