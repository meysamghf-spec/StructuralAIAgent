/**
 * Language + direction helpers for the chat thread.
 *
 * The backend writes Persian system cards for Persian conversations (backend/app/application/chat_i18n.py) and tags the
 * assistant message with `metadata.lang`. This module (1) decides the language/direction of every message, (2) translates
 * the UI chrome of the chat cards (buttons, state labels, card titles) and the common progress labels – including the
 * English labels stored in OLD messages and the live progress events that arrive before the final message – and
 * (3) isolates LTR runs (kN, m, 3.2 m, Mabhas 9, /workspace/model, file names) inside RTL text.
 */

export type ChatLang = "fa" | "en";

const ARABIC_SCRIPT = /[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]/g;
const LATIN_LETTER = /[A-Za-z]/g;

/** Persian when Arabic-script letters are at least a quarter of all letters (an English reply quoting one Persian word stays LTR). */
export function detectLang(text: string | null | undefined): ChatLang | null {
  const t = (text ?? "").replace(/\u061b/g, " ");
  const arabic = (t.match(ARABIC_SCRIPT) ?? []).length;
  const latin = (t.match(LATIN_LETTER) ?? []).length;
  if (arabic + latin === 0) {
    return null;
  }
  return arabic / (arabic + latin) >= 0.25 ? "fa" : "en";
}

export function isRtl(lang: ChatLang | null | undefined): boolean {
  return lang === "fa";
}

export function dirOf(lang: ChatLang | null | undefined): "rtl" | "ltr" {
  return isRtl(lang) ? "rtl" : "ltr";
}

/** Language of one chat message: the backend tag first, then the text itself, then the language of the conversation so far. */
export function messageLang(
  content: string,
  metadata?: Record<string, unknown> | null,
  fallback: ChatLang | null = null,
): ChatLang {
  const tagged = metadata?.lang;
  if (tagged === "fa" || tagged === "en") {
    return tagged;
  }
  return detectLang(content) ?? fallback ?? "en";
}

/** Language of the last user message that has letters (used for the live "processing" placeholder). */
export function conversationLang(messages: { role: string; content: string }[]): ChatLang {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user") {
      const lang = detectLang(messages[i].content);
      if (lang) {
        return lang;
      }
    }
  }
  return "en";
}

// ---- LTR isolation --------------------------------------------------------------------------------------------
export type BidiRun = { text: string; ltr: boolean };

// A path (/workspace/model), a parenthesised Latin group "(Mabahes Melli)", or a Latin word / number, optionally followed by more Latin words / numbers ("3.2 m", "kN m", "Mabhas 9").
const LTR_TOKEN = String.raw`(?:(?:\/[A-Za-z0-9_.\-]+)+\/?|\([A-Za-z0-9][A-Za-z0-9 _.,\-\/·×*%°²³^+=:]*\)|[A-Za-z0-9][A-Za-z0-9_\-./·×*%°²³^+=:]*)`;
const LTR_RUN = new RegExp(`${LTR_TOKEN}(?:[ \\u00a0]+${LTR_TOKEN})*`, "g");

/** Splits text into runs; Latin/number runs are `ltr` so they can be wrapped in `<bdi dir="ltr">` inside RTL text. */
export function splitBidiRuns(text: string): BidiRun[] {
  const runs: BidiRun[] = [];
  let last = 0;
  for (const match of text.matchAll(LTR_RUN)) {
    const index = match.index ?? 0;
    if (index > last) {
      runs.push({ text: text.slice(last, index), ltr: false });
    }
    runs.push({ text: match[0], ltr: true });
    last = index + match[0].length;
  }
  if (last < text.length) {
    runs.push({ text: text.slice(last), ltr: false });
  }
  return runs;
}

// ---- chrome / label dictionary --------------------------------------------------------------------------------
const FA: Record<string, string> = {
  // roles & message tools
  You: "شما",
  Agent: "دستیار",
  Copy: "کپی",
  "Copied ✓": "کپی شد ✓",
  Regenerate: "تولید دوباره",
  Stopped: "متوقف شد",
  "Assistant is responding": "دستیار در حال پاسخ است",
  "Processing your engineering request…": "درخواست مهندسی شما در حال پردازش است…",
  "↓ Latest": "↓ آخرین پیام",
  "Requires approval": "نیازمند تأیید",
  "Approval required": "تأیید لازم است",
  "Engineering outputs require review by a qualified professional before use in construction documents.":
    "خروجی‌های مهندسی پیش از استفاده در مدارک اجرایی باید توسط مهندس صاحب‌صلاحیت بازبینی شوند.",
  // cards
  "Agent progress": "پیشرفت دستیار",
  "Agent action": "اقدام دستیار",
  Context: "زمینه",
  "Context used for this response": "زمینه‌ی استفاده‌شده برای این پاسخ",
  "Hide details": "پنهان کردن جزئیات",
  "View details": "مشاهده‌ی جزئیات",
  "Try again": "تلاش دوباره",
  Download: "دانلود",
  Open: "باز کردن",
  Reason: "دلیل",
  Capability: "قابلیت",
  "Current step": "مرحله‌ی فعلی",
  // step / tool states
  Completed: "تکمیل شد",
  "In progress": "در حال انجام",
  Failed: "ناموفق",
  Pending: "در انتظار",
  complete: "تکمیل شد",
  current: "در حال انجام",
  error: "خطا",
  pending: "در انتظار",
  // statuses of a run
  completed: "تکمیل شد",
  in_progress: "در حال پردازش",
  awaiting_approval: "نیازمند تأیید",
  "awaiting approval": "نیازمند تأیید",
  blocked: "متوقف",
  failed: "ناموفق",
  rejected: "رد شد",
  cancelled: "لغو شد",
  queued: "در صف",
  "in progress": "در حال پردازش",
  "requires human approval": "نیازمند تأیید مهندس",
  // progress steps (also the live ones that arrive before the final, already-localized message)
  "Understanding request": "درک درخواست",
  "Loading project context": "بارگذاری زمینه‌ی پروژه",
  "Reading documents": "خواندن اسناد",
  "Reading attached files": "خواندن فایل‌های پیوست",
  "Running engineering workflow": "اجرای گردش‌کار مهندسی",
  "Validating results": "اعتبارسنجی نتایج",
  "Waiting for approval": "در انتظار تأیید",
  "Final response": "پاسخ نهایی",
  "Building engineering context": "ساخت زمینه‌ی مهندسی",
  "Awaiting human approval": "در انتظار تأیید انسانی",
  "Workflow failed": "گردش‌کار ناموفق بود",
  "Additional input required": "ورودی بیشتری لازم است",
  "Running structural analysis": "اجرای تحلیل سازه",
  "Running concrete design": "اجرای طراحی بتن",
  "Running steel design": "اجرای طراحی فولاد",
  "Generating CAD deliverables": "تولید خروجی‌های نقشه (CAD)",
  "Reading engineering documents": "خواندن اسناد مهندسی",
  "Preparing engineering report": "تهیه‌ی گزارش مهندسی",
  "Checking code compliance": "بررسی انطباق با آیین‌نامه",
  "Running optimization": "اجرای بهینه‌سازی",
  "Inspecting structural model": "بررسی مدل سازه",
  "Reviewing project loads": "بازبینی بارهای پروژه",
  "Evaluating seismic parameters": "ارزیابی پارامترهای لرزه‌ای",
  // errors
  "Engineering workflow failed": "گردش‌کار مهندسی ناموفق بود",
  "Request was rejected": "درخواست رد شد",
  "Request was cancelled": "درخواست لغو شد",
  "Additional input is required": "ورودی بیشتری لازم است",
  "Tool execution failed": "اجرای ابزار ناموفق بود",
  "The agent could not complete this engineering step.": "دستیار نتوانست این مرحله‌ی مهندسی را کامل کند.",
  // actions
  "Review approval": "بازبینی تأیید",
  "View Assistants": "مشاهده‌ی دستیارها",
  "View Results": "مشاهده‌ی نتایج",
  "View Reports": "مشاهده‌ی گزارش‌ها",
  "View Memory": "مشاهده‌ی حافظه",
  "View Traceability": "مشاهده‌ی ردیابی",
  "Current conversation": "گفتگوی فعلی",
  "Project context": "زمینه‌ی پروژه",
  // approval panel
  "Review required": "نیازمند بازبینی",
  "This work needs engineer approval before results are finalized. Decisions are recorded under your authenticated account":
    "این کار پیش از نهایی‌شدن نتایج به تأیید مهندس نیاز دارد. تصمیم‌ها با حساب احرازشده‌ی شما ثبت می‌شوند",
  "Open review link": "باز کردن پیوند بازبینی",
  Approve: "تأیید",
  Reject: "رد",
  "Approve result": "تأیید نتیجه",
  "Reject result": "رد نتیجه",
  "Optional note": "یادداشت اختیاری",
  "Rejection reason": "دلیل رد",
  // engineering result cards
  "Structural analysis results": "نتایج تحلیل سازه",
  "Structural analysis": "تحلیل سازه",
  "RC beam results": "نتایج تیر بتن‌آرمه",
  "RC beam analysis": "تحلیل تیر بتن‌آرمه",
  "Concrete design": "طراحی بتن",
  "ACI 318 RC beam check": "کنترل تیر بتن‌آرمه طبق ACI 318",
  Demo: "نمایشی",
  "Demo calculation": "محاسبه‌ی نمایشی",
  Assumptions: "فرض‌ها",
  Warnings: "هشدارها",
  "Required inputs": "ورودی‌های لازم",
  "Inputs and results": "ورودی‌ها و نتایج",
  "Inputs / parameters": "ورودی‌ها / پارامترها",
  Results: "نتایج",
  Validation: "اعتبارسنجی",
  Units: "واحدها",
  Input: "ورودی",
  Internal: "داخلی",
  Output: "خروجی",
  Code: "آیین‌نامه",
  "Calculation completed": "محاسبه انجام شد",
  "Design checks passed": "کنترل‌های طراحی قبول شد",
  "Design check failed": "کنترل طراحی مردود شد",
  "Graphical analysis becomes available after a valid engineering result is returned.":
    "تحلیل گرافیکی پس از دریافت نتیجه‌ی معتبر مهندسی نمایش داده می‌شود.",
  PASS: "قبول",
  FAIL: "مردود",
  "MISSING REQUIRED INPUT": "ورودی لازم ناقص است",
  "INVALID INPUT": "ورودی نامعتبر",
  "UNSUPPORTED CODE": "آیین‌نامه پشتیبانی نمی‌شود",
  // tool titles
  "Structural Analysis": "تحلیل سازه",
  "Concrete Design": "طراحی بتن",
  "Steel Design": "طراحی فولاد",
  "CAD Generation": "تولید نقشه (CAD)",
  "Document Analysis": "تحلیل اسناد",
  "Report Generation": "تولید گزارش",
  "Result Validation": "اعتبارسنجی نتایج",
  Optimization: "بهینه‌سازی",
  "Model Inspection": "بررسی مدل",
  "Load Assessment": "ارزیابی بارها",
  "Seismic Review": "بررسی لرزه‌ای",
  Indexed: "نمایه‌سازی شد",
  "Content extracted": "محتوا استخراج شد",
  "Model loaded": "مدل بارگذاری شد",
};

const VALIDATION_FA: Record<string, string> = {
  "Not Run": "اجرا نشده",
  "Pass": "قبول",
  "Warning": "هشدار",
  "Error": "خطا",
  "Requires Engineer Review": "نیازمند بازبینی مهندس",
  "Validated": "اعتبارسنجی شد",
  "Invalid": "نامعتبر",
  "Incomplete": "ناقص",
  "Partially Validated": "تا حدی اعتبارسنجی شد",
  "Requires Local Software": "نیازمند نرم‌افزار محلی",
};

const FA_PATTERNS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^Validation: (.+)$/, (m) => `اعتبارسنجی: ${VALIDATION_FA[m[1]] ?? m[1]}`],
  [/^Open (.+) Agent$/, (m) => `باز کردن دستیار ${FA_AGENT[m[1]] ?? m[1]}`],
  [/^Project: (.+)$/, (m) => `پروژه: ${m[1]}`],
  [/^(\d+) indexed documents?$/, (m) => `${m[1]} سند نمایه‌شده`],
  [/^(\d+) pages?$/, (m) => `${m[1]} صفحه`],
  [/^(.+) · (\d+) pages?$/, (m) => `${m[1]} · ${m[2]} صفحه`],
  [/^(\d+) relevant sections? found$/, (m) => `${m[1]} بخش مرتبط پیدا شد`],
  [/^(\d+) members? in model$/, (m) => `${m[1]} عضو در مدل`],
  [/^(\d+) load combinations? found$/, (m) => `${m[1]} ترکیب بار پیدا شد`],
  [/^(\d+) artifacts? produced$/, (m) => `${m[1]} خروجی تولید شد`],
  [/^Capability: (.+)$/, (m) => `قابلیت: ${m[1]}`],
  [/^Shear (PASS|FAIL)$/, (m) => `برش: ${m[1] === "PASS" ? "قبول" : "مردود"}`],
  [/^(Input|Internal|Output): (.+)$/, (m) => `${FA[m[1]]}: ${m[2]}`],
  [/^Code: (.+)$/, (m) => `آیین‌نامه: ${m[1]}`],
];

const FA_AGENT: Record<string, string> = {
  "Structural Modeling": "مدل‌سازی سازه",
  "Load Assessment": "ارزیابی بارها",
  Analysis: "تحلیل",
  "Concrete Design": "طراحی بتن",
  "Steel Design": "طراحی فولاد",
  Optimization: "بهینه‌سازی",
  Seismic: "لرزه‌ای",
  Validation: "اعتبارسنجی",
  CAD: "نقشه‌کشی (CAD)",
  Reporting: "گزارش‌دهی",
  "Document Interpretation": "تفسیر اسناد",
  "Prompt Generation": "تولید درخواست",
  "Structural Engineering": "مهندسی سازه",
};

/** Persian text for a known UI/label string; unknown strings (and every non-fa language) come back unchanged. */
export function chatT(lang: ChatLang | null | undefined, text: string): string {
  if (lang !== "fa" || !text) {
    return text;
  }
  const spaced = text.replace(/_/g, " ");
  const hit = FA[text] ?? FA[spaced] ?? FA[spaced.toLowerCase()];
  if (hit !== undefined) {
    return hit;
  }
  for (const [pattern, fn] of FA_PATTERNS) {
    const m = text.match(pattern);
    if (m) {
      return fn(m);
    }
  }
  return text;
}
