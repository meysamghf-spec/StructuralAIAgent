"""Route chat requests like "convert this PDF to DXF" to the AutoCAD tools."""
from __future__ import annotations

import re
from urllib.parse import quote

_CAD = re.compile(r"\b(dxf|dwg|autocad|cad)\b|اتوکد|اتوکـد|نقشه\s*(کد|cad)|دی\s*ایکس\s*اف", re.I)
_CONVERT = re.compile(r"convert|vectori[sz]e|pdf|image|photo|picture|scan|تبدیل|عکس|تصویر|پی\s*دی\s*اف|اسکن", re.I)


def autocad_chat_reply(text: str) -> str | None:
    if not _CAD.search(text or ""):
        return None
    if _CONVERT.search(text):
        return (
            "**PDF / image → DXF**\n\n"
            "Open [Integrations → AutoCAD](/integrations#autocad), choose *PDF or image → DXF*, and upload the plan "
            "(camera, gallery or file). You get a layered DXF and a preview, then accept or flag it before it is used as a model.\n\n"
            "برای تبدیل PDF یا عکس نقشه به DXF به [Integrations → AutoCAD](/integrations#autocad) بروید و فایل را بارگذاری کنید."
        )
    link = f"/integrations?cad_prompt={quote(text[:500])}#autocad"
    return (
        "**Prompt → drawing**\n\n"
        f"[Open this prompt in Integrations → AutoCAD]({link}) to generate a floor-plan DXF with a preview.\n\n"
        f"برای ساخت نقشه‌ی DXF از این متن، [اینجا]({link}) را باز کنید."
    )
