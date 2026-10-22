"""Run AutoCAD tools straight from the main chat: PDF/photo attachment -> DXF, drawing prompt -> DXF."""
from __future__ import annotations

import re
from typing import Any, Callable

_CAD = re.compile(r"\b(dxf|dwg|autocad|cad)\b|اتوکد|اتوکـد|دی\s*ایکس\s*اف", re.I)
_CONVERT = re.compile(r"convert|vectori[sz]e|trace|digiti[sz]e|تبدیل|وکتور|رسم\s*کن|دیجیتال", re.I)
_DRAW = re.compile(
    r"floor\s*plan|draw\s+(me\s+)?(a|an|the)?\s*\w*\s*(plan|layout|house|apartment|villa)|architectural\s+plan|"
    r"پلان|نقشه\s*(ی|‌ی)?\s*(معماری|آپارتمان|خانه|ویلا|طبقه)|نقشه.*(بکش|بساز|ترسیم|طراحی)|(بکش|ترسیم|طراحی\s*کن).*نقشه",
    re.I,
)
_VECTOR_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
_DEFAULT_ATTACH_TEXT = "Please review the attached file(s)"


def wants_vectorize(text: str, filenames: list[str]) -> bool:
    if not any(f.lower().endswith(_VECTOR_EXT) for f in filenames):
        return False
    t = text or ""
    return bool(_CAD.search(t) or _CONVERT.search(t) or re.search(r"نقشه|پلان|plan|drawing", t, re.I))


def wants_prompt(text: str) -> bool:
    t = text or ""
    if _CONVERT.search(t) and re.search(r"pdf|image|photo|عکس|تصویر|پی\s*دی\s*اف|اسکن", t, re.I):
        return False
    return bool(_DRAW.search(t) or (_CAD.search(t) and re.search(r"plan|room|bed|apartment|house|نقشه|اتاق|خواب|واحد", t, re.I)))


def _fa(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def run_chat_autocad(
    text: str,
    attachments: list[tuple[str, Callable[[], bytes]]],
    *,
    owner: str,
    project_id: str | None,
    save_project_file: Callable[[str, bytes], str | None] | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Return (markdown, metadata) when the message is an AutoCAD job, else None."""
    from . import service

    names = [n for n, _ in attachments]
    fa = _fa(text)
    try:
        if wants_vectorize(text, names):
            name, read = next((n, r) for n, r in attachments if n.lower().endswith(_VECTOR_EXT))
            from .vectorize import vectorize

            doc, summary = vectorize(read(), name)
            job = service.save_job(doc, summary, kind="vectorize", owner=owner, source=name, project_id=project_id)
            title = f"تبدیل {name} به DXF" if fa else f"{name} → DXF"
        elif not attachments and wants_prompt(text):
            from .floor_plan import generate_from_prompt

            try:
                doc, summary = generate_from_prompt(text)
            except Exception:  # noqa: BLE001 - brief lacks storeys/footprint: fill sensible defaults
                doc, summary = generate_from_prompt(f"{text}. 1-storey residential building 12x15 m")
            job = service.save_job(doc, summary, kind="prompt", owner=owner, source=text, project_id=project_id)
            title = "نقشه از متن" if fa else "Drawing from prompt"
        else:
            return None
    except Exception as exc:  # noqa: BLE001 - tell the user instead of falling through to generic chat
        msg = (f"نتوانستم این نقشه را بسازم: {exc}" if fa else f"I could not produce a DXF from this: {exc}")
        return msg, {"mode": "rule_based", "intent": "autocad", "autocad_error": str(exc)[:300]}

    filename = f"autocad-{job['kind']}-{job['id'][:8]}.dxf"
    file_id = None
    if save_project_file and project_id:
        try:
            dxf = (service._root() / job["id"] / "drawing.dxf").read_bytes()
            file_id = save_project_file(filename, dxf)
            if file_id:
                service.set_project_file(job["id"], file_id)
        except Exception:  # noqa: BLE001 - the job is still available from the CAD page
            file_id = None
    s = job.get("summary", {})
    lines = [f"**{title}**", ""]
    for k, v in list(s.items())[:6]:
        if isinstance(v, (int, float, str)):
            lines.append(f"- {k.replace('_', ' ')}: {v}")
    if job["kind"] == "vectorize":
        lines.append("")
        lines.append("لطفاً نقشه را بررسی کنید و تأیید یا علامت‌گذاری کنید." if fa
                     else "Check the preview, then accept it or flag a problem before using it as a model.")
    if file_id:
        lines.append("")
        lines.append(f"فایل {filename} در فایل‌های پروژه ذخیره شد." if fa else f"Saved to project files as `{filename}`.")
    meta = {"mode": "rule_based", "intent": "autocad",
            "autocad_result": {"job_id": job["id"], "kind": job["kind"], "title": title, "filename": filename,
                               "layers": job.get("layers", []), "summary": s, "review": job["review"],
                               "project_file_id": file_id}}
    return "\n".join(lines), meta


def autocad_chat_reply(text: str) -> str | None:  # kept for API compatibility; chat now runs jobs directly
    return None
