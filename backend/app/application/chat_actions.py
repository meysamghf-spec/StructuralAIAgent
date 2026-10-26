"""Deterministic chat commands: everything the UI can do must also be doable by typing (English, Persian, Finglish).

Parsers are pure (unit-tested); executors reuse the real engines/services. No engineering number is invented here:
downloads rebuild the stored run inputs, project/approval commands call the same services as the REST routes.
Engineering-input edits and analysis/design/optimisation/validation runs stay with the frame3d + agent engines
(see frame3d_followup / frame3d_chat_analysis); this module covers outputs, projects, assistants and approvals.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any
from uuid import UUID

from app.application import frame3d_followup as fu

_ZWNJ = "\u200c"


def _n(text: str) -> str:
    t = fu.norm(text or "").lower().replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", t.replace(_ZWNJ, " ")).strip()


def is_fa(text: str) -> bool:
    return any("\u0600" <= c <= "\u06ff" for c in text or "")


# ------------------------------------------------------------------------------------------- downloads
_DL_VERB = (r"download|دانلود|export|اکسپورت|get me|give me|send me|generate|produce|save|\bzip\b|زیپ|بده|بدی|بگیر|بفرست|بساز|تهیه کن|"
            r"بزن|درآور|دراور|خروجی بگیر|\bpdf\b|\bbede\b|\bbegir\b|\bbede(?:h)?\b|\bdownload\b")
# "detail the rebar" / "دیتیلینگ آرماتور را بده": the Detailing step that follows Design (maps to the rebar DXF sheets)
_DETAIL_CMD = (r"\bdetail(?:ing)? (?:the |my |all )?(?:rebars?|reinforcement|bars|members|beams|columns)\b|\brebar detailing\b|"
               r"دیتیل(?:ینگ)?|جزئیات ?سازی|جزییات ?سازی")
_DETAIL_QUESTION = (r"[?؟]\s*$|^(?:what|why|how|when|which|is|are|does|do|can you explain|explain)\b|چیست|چطور|چگونه|چرا|یعنی چه|توضیح بده")
_ALL_NOUN = (r"(?:all|every|everything|whole|complete|full)\b.{0,24}(?:output|result|file|deliverable|package|document)s?|"
             r"\b(?:outputs?|deliverables?|results? package|package|bundle|zip)\b|همه.{0,12}(?:خروجی|فایل|نتایج|مدارک)|"
             r"خروجی ?ها|خروجی های|زیپ|پکیج|بسته|(?:همه|تمام)\b|نتایج|\beverything\b")
_SPECIFIC: list[tuple[str, str, str, str, str]] = [
    # pattern, kind, name, format, label (en)
    (r"etabs|\be2k\b|ایتبس|ای ?تبس", "model", "e2k", "e2k", "ETABS model (.e2k)"),
    (r"\bsafe\b|\bf2k\b|سیف|سیفی", "model", "f2k", "f2k", "SAFE model (.f2k)"),
    (r"sap ?2000|\bsap\b|\bs2k\b|ساپ", "model", "s2k", "s2k", "SAP2000 model (.s2k)"),
    (r"نقشه (?:های )?اجرایی|structural (?:drawing )?set|construction drawings|شیت", "drawing", "structural_set", "pdf", "Structural drawing set (PDF)"),
    (r"آرماتور ?بندی|rebar|bar bending|reinforcement detail|میلگرد|دیتیل(?:ینگ)?|جزئیات ?سازی|جزییات ?سازی", "drawing", "dxf_rebar", "dxf", "Rebar details (DXF)"),
    (r"نقشه (?:ی )?(?:فونداسیون|پی)|foundation (?:drawing|detail|plan)", "drawing", "dxf_foundation", "dxf", "Foundation details (DXF)"),
    (r"\bdxf\b|autocad|auto ?cad|\bcad\b|اتوکد|اتو کد|نقشه|پلان", "drawing", "dxf_plans", "dxf", "Plans (DXF)"),
    (r"excel|xlsx|اکسل|جدول|tables?|spreadsheet", "table", "all", "xlsx", "All tables (Excel)"),
    (r"figures?|images?|diagram|png|تصویر|عکس|نمودار|شکل", "figure", "view3d", "png", "3D view (PNG)"),
    (r"گزارش|report|calculation", "report", "report_pdf", "pdf", "Calculation report (PDF)"),
    (r"\bjson\b|raw results|نتایج خام", "report", "report_json", "json", "Raw results (JSON)"),
]
_FA_LABEL = {"e2k": "مدل ETABS", "f2k": "مدل SAFE", "s2k": "مدل SAP2000", "structural_set": "نقشه‌های اجرایی سازه (PDF)",
             "dxf_rebar": "جزئیات آرماتوربندی (DXF)", "dxf_foundation": "جزئیات فونداسیون (DXF)", "dxf_plans": "پلان‌ها (DXF)",
             "all": "همهٔ جداول (Excel)", "view3d": "نمای سه‌بعدی (PNG)", "report_pdf": "گزارش محاسبات (PDF)",
             "report_json": "نتایج خام (JSON)"}
_FIGURES_ALL = [("view3d", "3D view"), ("deformed", "Deformed shape"), ("moment", "Moment diagram"), ("shear", "Shear diagram"),
                ("axial", "Axial force diagram"), ("drift", "Drift plot")]
_FA_FIG = {"view3d": "نمای سه‌بعدی", "deformed": "شکل تغییرشکل‌یافته", "moment": "نمودار لنگر", "shear": "نمودار برش",
           "axial": "نمودار نیروی محوری", "drift": "نمودار دریفت"}


def parse_download(text: str) -> dict[str, Any] | None:
    """-> {"zip": bool, "items": [{kind,name,format,label}]} when the user asks to get / download outputs, else None."""
    t = _n(text)
    if not t or len(t) > 200:
        return None
    detail_cmd = bool(re.search(_DETAIL_CMD, t))
    if not re.search(_DL_VERB, t) and not detail_cmd:
        return None
    if detail_cmd and not re.search(_DL_VERB, t) and re.search(_DETAIL_QUESTION, t):
        return None  # "what is rebar detailing?" is a question, not a command
    # reading / extracting from documents is not a request for outputs ("extract requirements from the specification PDF")
    if re.search(r"\b(?:extract|summari[sz]e|read|parse|review|ocr)\b|استخراج|خلاصه|بخوان|بررسی کن", t) and not re.search(r"download|دانلود|\bzip\b|زیپ", t):
        return None
    # model-building prompts ("3 storey frame ... export to ETABS") are handled by the frame engine, not here
    from app.application.frame3d_chat_analysis import is_frame3d_request

    if is_frame3d_request(text):
        return None
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for pat, kind, name, fmt, label in _SPECIFIC:
        if re.search(pat, t) and name not in seen:
            if name == "dxf_plans" and ({"dxf_rebar", "dxf_foundation", "structural_set"} & seen) and not re.search(r"\bdxf\b|autocad|cad|اتوکد", t):
                continue
            seen.add(name)
            items.append({"kind": kind, "name": name, "format": fmt, "label": label})
    if "view3d" in seen:  # «تصویر/نمودارها» -> every figure
        items = [i for i in items if i["name"] != "view3d"] + [
            {"kind": "figure", "name": n, "format": "png", "label": f"{lab} (PNG)"} for n, lab in _FIGURES_ALL]
    if "report_pdf" in seen and "report_json" not in seen and re.search(r"markdown|\.md\b", t):
        items.append({"kind": "report", "name": "report_md", "format": "md", "label": "Calculation report (Markdown)"})
    if re.search(r"\b(?:pdf)\b", t) and not (seen & {"report_pdf", "structural_set", "dxf_plans", "dxf_rebar", "dxf_foundation"}):
        items.append({"kind": "report", "name": "report_pdf", "format": "pdf", "label": "Calculation report (PDF)"})
    explicit_all = bool(re.search(_ALL_NOUN, t)) or bool(re.fullmatch(r"(?:please )?(?:download|دانلود)(?: کن| کنید)?", t))
    if items and not (explicit_all and re.search(r"\b(?:all|every|everything)\b|همه|تمام|زیپ|\bzip\b", t)):
        return {"zip": False, "items": items}
    if explicit_all:
        return {"zip": True, "items": []}
    return None


_PLAN_FALLBACK = [
    {"kind": "table", "name": "all", "format": "xlsx", "label": "All tables (Excel)"},
    {"kind": "figure", "name": "view3d", "format": "png", "label": "3D view (PNG)"},
    {"kind": "report", "name": "report_pdf", "format": "pdf", "label": "Calculation report (PDF)"},
]


def _export_allowed(item: dict[str, str], exports: Any) -> bool:
    if exports is True or exports is None:
        return True
    allowed = set(exports or [])
    if item["kind"] == "model":
        return item["name"] in allowed
    if item["kind"] == "drawing":
        return "dxf" in allowed
    return True


def apply_plan(spec: dict[str, Any], exports: Any, fa: bool = False) -> tuple[dict[str, Any], list[str]]:
    """Keep only what the account's plan can export (the download endpoints would answer 402 otherwise).

    -> (spec, names of the withheld outputs). `exports` is the plan's "exports" limit (list / True / None = unlimited)."""
    if exports is True or exports is None:
        return spec, []
    if spec["zip"]:
        if "dxf" in set(exports or []):
            return spec, []
        return {"zip": False, "items": [dict(i) for i in _PLAN_FALLBACK]}, (["فایل‌های مدل (ETABS/SAFE/SAP2000)", "نقشه‌های DXF/PDF"] if fa else ["model files (ETABS/SAFE/SAP2000)", "DXF/PDF drawings"])
    kept = [i for i in spec["items"] if _export_allowed(i, exports)]
    withheld = [(_FA_LABEL.get(i["name"]) if fa else None) or i["label"] for i in spec["items"] if not _export_allowed(i, exports)]
    if withheld and not kept:
        kept = [dict(i) for i in _PLAN_FALLBACK]
    return {"zip": False, "items": kept}, withheld


def downloads_reply(spec: dict[str, Any], inputs: dict[str, Any], *, fa: bool, assumed: list[str] | None = None,
                    project_id: str | None = None, withheld: list[str] | None = None) -> tuple[str, dict[str, Any]]:
    lang_fa = fa
    if spec["zip"]:
        head = ("همهٔ خروجی‌ها در یک فایل ZIP آماده است: جداول (Excel/CSV)، نمودارها، مدل‌های ETABS/SAFE/SAP2000، نقشه‌های DXF و PDF، و گزارش محاسبات."
                if lang_fa else "All outputs are ready as one ZIP: tables (Excel/CSV), figures, ETABS/SAFE/SAP2000 models, DXF + PDF drawings and the calculation report.")
        lines = [head, "", "دانلود از دکمهٔ زیر شروع می‌شود." if lang_fa else "The download starts from the button below."]
    else:
        names = [(_FA_FIG.get(i["name"]) if i["kind"] == "figure" else _FA_LABEL.get(i["name"])) if lang_fa else i["label"] for i in spec["items"]]
        names = [n or i["label"] for n, i in zip(names, spec["items"])]
        lines = ["فایل‌های درخواستی آماده است:" if lang_fa else "Your files are ready:", ""] + [f"- {n}" for n in names]
    if assumed:
        lines += ["", ("فرض‌ها: مدلی در این گفتگو/پروژه نبود، پس با مقادیر پیش‌فرض ساخته شد — " if lang_fa else
                       "Assumptions: no model existed in this chat/project, so the files use typical defaults — ") + ", ".join(assumed)
                  + ("؛ می‌توانید مدل را عوض کنید و دوباره درخواست بدهید." if lang_fa else ". Change the model and ask again to regenerate.")]
    if withheld:
        lines += ["", ("طرح فعلی شما این خروجی‌ها را شامل نمی‌شود: " if lang_fa else "Your current plan doesn't include: ")
                  + ", ".join(withheld) + (". به جای آن‌ها بقیهٔ خروجی‌ها آماده است؛ برای دریافتشان طرح را ارتقا دهید."
                                           if lang_fa else ". Everything else is ready — upgrade the plan to get them.")]
    shown = [{**i, "label": (_FA_FIG.get(i["name"]) if i["kind"] == "figure" else _FA_LABEL.get(i["name"])) or i["label"]}
             for i in spec["items"]] if lang_fa else spec["items"]
    meta = {"mode": "rule_based", "intent": "chat_downloads",
            "chat_downloads": {"zip": spec["zip"], "items": shown, "inputs": inputs, "project_id": project_id,
                               "lang": "fa" if lang_fa else "en", "assumed": assumed or []}}
    return "\n".join(lines), meta


def default_frame_inputs(fa: bool = False) -> tuple[dict[str, Any], list[str]]:
    from app.application.frame3d_chat_analysis import Frame3dInputs

    inp = Frame3dInputs()
    assumed = fu.apply_defaults(inp)
    d = {k: v for k, v in asdict(inp).items() if k != "parsed"}
    if fa:
        names = {"storeys": f"{inp.storeys} طبقه", "bays_x": f"{inp.bays_x} دهانه در جهت X", "bays_y": f"{inp.bays_y} دهانه در جهت Y",
                 "bay_x_m": f"دهانه‌های {inp.bay_x_m:g} متری", "storey_height_m": f"ارتفاع طبقه {inp.storey_height_m:g} متر"}
        codes = "آیین‌نامه‌های ایران (۲۸۰۰ / مبحث ۹)"
    else:
        names = {"storeys": f"{inp.storeys} storeys", "bays_x": f"{inp.bays_x} bays X", "bays_y": f"{inp.bays_y} bays Y",
                 "bay_x_m": f"{inp.bay_x_m:g} m bays", "storey_height_m": f"{inp.storey_height_m:g} m storey height"}
        codes = "Iranian codes (2800 / Mabhas 9)"
    return d, [names[k] for k in ("storeys", "bays_x", "bays_y", "bay_x_m", "storey_height_m") if k in names] + [codes]


# ------------------------------------------------------------------------------------------- projects
_NAME = r"[\"“«']?\s*([^\"”»'\n]{1,80}?)\s*[\"”»']?"


def parse_project_command(text: str) -> dict[str, Any] | None:
    t = _n(text)
    if not t or len(t) > 160:
        return None
    raw = fu.norm(text).replace(_ZWNJ, " ").strip()
    m = (re.search(rf"(?:create|make|start|new|add)\s+(?:a\s+|an\s+)?(?:new\s+)?project(?:\s+(?:called|named|name|:))?\s*{_NAME}$", raw, re.I)
         or re.search(rf"(?:پروژه(?:\s*ی)?\s*(?:جدید(?:ی)?)?)\s*(?:به\s*نام|با\s*نام|:)?\s*{_NAME}\s*(?:را\s*)?(?:بساز|ایجاد\s*کن|بزن|شروع\s*کن|درست\s*کن)$", raw)
         or re.search(rf"(?:یک|یه)\s*پروژه\s*(?:جدید\s*)?(?:به\s*نام|با\s*نام)?\s*{_NAME}\s*(?:بساز|ایجاد\s*کن|درست\s*کن)$", raw)
         or re.search(rf"^(?:new project|پروژه جدید)\s*[:\-]?\s*{_NAME}$", raw, re.I))
    if m:
        name = re.sub(r"^(?:called|named|name|به نام|با نام)\s+", "", m.group(1).strip(), flags=re.I).strip(" .،:-")
        name = re.sub(r"\s+(?:را|رو)$", "", name)
        if name and not re.fullmatch(r"(?:جدید|new|project|پروژه)", name, re.I):
            return {"kind": "create", "name": name[:80]}
        return {"kind": "create", "name": ""}
    m = (re.search(rf"(?:open|switch to|go to|select|use|load)\s+(?:the\s+)?project\s*(?:called|named|:)?\s*{_NAME}$", raw, re.I)
         or re.search(rf"پروژه(?:\s*ی)?\s*{_NAME}\s*(?:را|رو)?\s*(?:باز\s*کن|انتخاب\s*کن|فعال\s*کن|بیاور|برو)$", raw)
         or re.search(rf"(?:برو (?:به|توی|تو) |باز کردن )پروژه\s*{_NAME}$", raw))
    if m and m.group(1).strip():
        return {"kind": "open", "name": m.group(1).strip(" .،:")}
    if re.search(r"(?:list|show|what(?:'s| are)?)\s+(?:all\s+)?(?:my\s+)?projects|my projects|پروژه ?(?:ها|های) ?(?:من|م)|لیست پروژه|پروژه ها را (?:نشان|نمایش) بده|نشان بده.{0,10}پروژه", t):
        return {"kind": "list"}
    return None


def _project_line(p: Any) -> str:
    return f"- {p.name} (`{str(p.id)[:8]}`)"


# ------------------------------------------------------------------------------------------- assistants
_ASSIST_ALIASES: list[tuple[str, str]] = [
    (r"model(?:l?ing)?|مدل ?سازی|مدلسازی", "STRUCTURAL_MODELING_AGENT"),
    (r"load|بار(?:گذاری)?", "LOAD_ASSESSMENT_AGENT"),
    (r"analysis|analy[sz]e|تحلیل", "ANALYSIS_AGENT"),
    (r"concrete|rc\b|بتن", "CONCRETE_DESIGN_AGENT"),
    (r"steel|فولاد", "STEEL_DESIGN_AGENT"),
    (r"seismic|earthquake|لرزه|زلزله", "SEISMIC_AGENT"),
    (r"validat|اعتبار ?سنجی|کنترل طرح", "VALIDATION_AGENT"),
    (r"\bcad\b|drawing|نقشه", "CAD_AGENT"),
    (r"report|گزارش", "REPORTING_AGENT"),
    (r"document|مدارک|سند", "DOCUMENT_INTERPRETATION_AGENT"),
    (r"optimi[sz]|بهینه", "OPTIMIZATION_AGENT"),
    (r"(?:structural )?engineering|عمومی|اصلی|general|auto\b|خودکار", "STRUCTURAL_ENGINEERING_AGENT"),
]


def parse_assistant_switch(text: str) -> str | None:
    t = _n(text)
    if not t or len(t) > 100:
        return None
    if not re.search(r"(?:switch|change|use|select|choose|talk to|ask|go to|open)\b.{0,20}\b(?:assistant|agent)\b|\b(?:assistant|agent)\b.{0,20}(?:switch|select)|"
                     r"دستیار|عامل", t):
        return None
    if re.search(r"create|build|new agent|new assistant|بساز|ایجاد", t):
        return None  # agent builder, not a switch
    if not re.search(r"switch|change|use|select|choose|talk|ask|go to|open|انتخاب|عوض|تغییر|برو|بیاور|فعال|استفاده|سراغ|با ", t):
        return None
    for pat, agent in _ASSIST_ALIASES:
        if re.search(pat, t):
            return agent
    return None


# ------------------------------------------------------------------------------------------- approvals
def parse_approval_command(text: str) -> dict[str, Any] | None:
    t = _n(text)
    if not t or len(t) > 160:
        return None
    ref = r"(?:the\s+)?(?:pending\s+)?(?:run|request|approval|result|design|model|analysis|it|this|that|all|everything)?"
    if re.search(r"(?:show|list|what).{0,16}(?:pending )?approvals?|pending approvals?|تاییدیه ?(?:ها|های)|(?:درخواست|موارد) (?:های )?(?:منتظر|در انتظار)|منتظر تایید", t):
        return {"kind": "list"}
    t = re.sub(r"^(?:ok|okay|yes|sure|بله|باشه|اوکی)[,. ]+", "", t)
    if re.match(rf"^(?:please\s+)?(?:approve|accept|sign off(?: on)?|confirm)\s*{ref}\s*(?:#?\d+)?[.!]?$", t) or re.match(
            r"^(?:(?:این|آن|همه|آخرین)(?: را| رو)? )?(?:تایید|تاييد|تأیید|قبول)(?: کن| کنید| می کنم| میکنم| است)?$|^(?:تایید|تأیید) (?:همه|این|آخرین)(?: را| رو)?$", t):
        return {"kind": "approve", "all": bool(re.search(r"\ball\b|everything|همه", t)), "index": _index(t)}
    m = re.match(rf"^(?:please\s+)?(?:reject|decline|deny|disapprove)\s*{ref}\s*(?:#?\d+)?\s*(?:because|since|reason:?|:|-)?\s*(.*)$", t) or re.match(
        r"^(?:رد|رد کن|رد کنید|مردود)(?: ?کن| ?کنید)?(?: این| آن| همه)?\s*(?:چون|به دلیل|دلیل:?|:|-)?\s*(.*)$", t)
    if m:
        return {"kind": "reject", "all": bool(re.search(r"\ball\b|همه", t)), "index": _index(t), "reason": (m.group(1) or "").strip() or "Rejected via chat"}
    return None


def _index(t: str) -> int | None:
    m = re.search(r"#?\b(\d{1,2})\b", t)
    return int(m.group(1)) if m else None


def run_approval(cmd: dict[str, Any], *, project_id: UUID | None, account_id: str, fa: bool) -> tuple[str, dict[str, Any]]:
    from app.application.service_factory import build_human_approval_service

    if project_id is None:
        return ("برای تایید/رد باید یک پروژه انتخاب شده باشد؛ بنویسید «پروژه … را باز کن»." if fa else
                "Open a project first (say “open project <name>”) so I know which approvals you mean."), {"mode": "rule_based", "intent": "approvals", "needs": "project"}
    svc = build_human_approval_service()
    pending = list(svc.list_pending(project_id))
    pending.sort(key=lambda r: r.created_at, reverse=True)
    meta: dict[str, Any] = {"mode": "rule_based", "intent": "approvals",
                            "actions": [{"href": "/workspace/approvals", "label": "Open Approvals"}]}
    if not pending:
        return ("هیچ مورد منتظر تایید در این پروژه نیست." if fa else "There is nothing waiting for approval in this project."), meta
    if cmd["kind"] == "list":
        lines = ["موارد منتظر تایید:" if fa else "Waiting for approval:", ""] + [f"{i}. {r.summary}" for i, r in enumerate(pending, 1)]
        lines += ["", "بنویسید «تایید کن» (جدیدترین)، «همه را تایید کن» یا «رد کن چون …»." if fa else
                  "Say “approve” (newest), “approve all”, or “reject because …”."]
        return "\n".join(lines), meta
    if cmd["all"]:
        targets = pending
    elif cmd.get("index") and 1 <= cmd["index"] <= len(pending):
        targets = [pending[cmd["index"] - 1]]
    else:
        targets = pending[:1]  # assumed: the newest pending item (stated in the reply)
    done: list[str] = []
    for r in targets:
        if cmd["kind"] == "approve":
            svc.approve_request(project_id, r.id, approver=account_id, decision_note="Approved via chat")
        else:
            svc.reject_request(project_id, r.id, approver=account_id, rejection_reason=cmd.get("reason") or "Rejected via chat")
            try:
                from app.application import revision_workflow

                revision_workflow.handle_rejection(svc, project_id, r, cmd.get("reason") or "Rejected via chat", account_id)
            except Exception:  # noqa: BLE001 - the decision itself is recorded; the follow-up revision is best effort
                pass
        done.append(r.summary)
    verb = ("تایید شد" if cmd["kind"] == "approve" else "رد شد") if fa else ("Approved" if cmd["kind"] == "approve" else "Rejected")
    lines = [f"{verb}:" if fa else f"{verb}:", ""] + [f"- {s}" for s in done]
    if len(targets) < len(pending):
        lines += ["", (f"{len(pending) - len(targets)} مورد دیگر هنوز منتظر است؛ فرض من جدیدترین مورد بود." if fa else
                       f"{len(pending) - len(targets)} more item(s) are still waiting; I assumed you meant the newest one (say “approve all” for the rest).")]
    meta["approval_decision"] = {"decision": cmd["kind"], "count": len(done)}
    return "\n".join(lines), meta
