// App-shell UI language (sidebar, chat dock, frame panels); result cards follow the prompt language.
import { makeT, type Frame3dLang } from "./frame3d-i18n";

const KEY = "sa.uiLang";
export const UI_LANG_EVENT = "sa:ui-lang";

export function getUiLang(): Frame3dLang {
  if (typeof window === "undefined") return "en";
  try {
    return window.localStorage.getItem(KEY) === "fa" ? "fa" : "en";
  } catch {
    return "en";
  }
}

export function setUiLang(lang: Frame3dLang): void {
  try {
    window.localStorage.setItem(KEY, lang);
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent(UI_LANG_EVENT, { detail: lang }));
}

export const UI_FA: Record<string, string> = {
  "Welcome back": "خوش آمدید",
  "Chat with your structural AI": "با هوش مصنوعی سازه‌ات گفتگو کن",
  "Analysis, design, validation, approval and memory — all in one conversation.": "تحلیل، طراحی، اعتبارسنجی، تأیید و حافظه — همه در یک گفتگو.",
  "Chat-first, AI-driven structural engineering": "مهندسی سازهٔ گفتگومحور و مبتنی بر هوش مصنوعی",
  "Sign in to chat with your structural AI.": "وارد شوید و با هوش مصنوعی سازه‌تان گفتگو کنید.",
  "Create an account to chat with your structural AI — analysis, design, validation, approval and memory.": "حساب بسازید و با هوش مصنوعی سازه‌تان گفتگو کنید — تحلیل، طراحی، اعتبارسنجی، تأیید و حافظه.",
  Chat: "گفتگو", Projects: "پروژه‌ها", "New Project": "پروژهٔ جدید", Model: "مدل", Files: "فایل‌ها", Memory: "حافظه", Learning: "یادگیری",
  Assistants: "دستیارها", "Assistant Builder": "سازندهٔ دستیار", Approvals: "تأییدها", Analysis: "تحلیل",
  Results: "نتایج", Design: "طراحی", Optimization: "بهینه‌سازی", Integrations: "اتصال نرم‌افزارها", CAD: "نقشه (CAD)",
  Validation: "اعتبارسنجی", Reports: "گزارش‌ها", Traceability: "ردیابی", Upgrades: "ارتقا", "AI Assistant": "دستیار هوشمند", "Platform Issues": "مشکلات پلتفرم", Foundation: "فونداسیون",
  "Signed in": "وارد شده", "Sign out": "خروج", "Sign in": "ورود", "Project chat": "گفتگوی پروژه", "Open chat": "باز کردن گفتگو",
  "Close chat": "بستن گفتگو", "No project selected": "پروژه‌ای انتخاب نشده", Project: "پروژه",
  "Quick 3D frame model": "مدل سریع قاب سه‌بعدی", Geometry: "هندسه", Sections: "مقاطع", Materials: "مصالح", Loads: "بارها",
  "Seismic (2800)": "زلزله (۲۸۰۰)", "Design & foundation": "طراحی و فونداسیون", Stories: "تعداد طبقات", "Bays in X": "تعداد دهانه X",
  "Bays in Y": "تعداد دهانه Y", "Span X": "طول دهانه X", "Span Y": "طول دهانه Y", "Story height": "ارتفاع طبقه",
  "Column b": "عرض ستون b", "Column h": "عمق ستون h", "Beam b": "عرض تیر b", "Beam h": "ارتفاع تیر h", "Slab thickness": "ضخامت دال",
  "Dead load": "بار مرده", "Live load": "بار زنده", "Roof live load": "بار زندهٔ بام", "Perimeter wall": "دیوار پیرامونی",
  "Seismic code": "آیین‌نامهٔ زلزله", "Seismic hazard": "خطر نسبی زلزله", "Soil type": "نوع خاک", "Importance I": "ضریب اهمیت I",
  "Lateral system": "سیستم باربر جانبی", "C (if assumed)": "C (در صورت فرض)", "Allowable bearing": "تنش مجاز خاک",
  "Import from last chat frame": "دریافت از آخرین قاب گفتگو", "Reset to defaults": "بازگشت به پیش‌فرض",
  "Run analysis + design": "اجرای تحلیل و طراحی", "Running…": "در حال اجرا…", "Saved to this project.": "برای این پروژه ذخیره شد.",
  "This model is incomplete": "این مدل ناقص است",
  "Some required inputs are missing. I can complete them with typical values (4 storeys, 3×3 bays of 5 m, 3.2 m storey height, Iranian codes) and re-run; the assumptions are listed in the result.": "برخی ورودی‌های لازم کم است. می‌توانم با مقادیر معمول (۴ طبقه، ۳×۳ دهانه ۵ متری، ارتفاع طبقه ۳.۲ متر، آیین‌نامه‌های ایران) کامل کنم و دوباره اجرا کنم؛ فرض‌ها در نتیجه فهرست می‌شوند.",
  "Complete with defaults and run": "تکمیل با پیش‌فرض‌ها و اجرا",
  "No 3D frame result yet. Build one on the Model page or describe a frame in the chat.":
    "هنوز نتیجهٔ قاب سه‌بعدی وجود ندارد. در صفحهٔ مدل یک قاب بسازید یا آن را در گفتگو توصیف کنید.",
  "No chat frame found for this project yet.": "هنوز قابی در گفتگوی این پروژه ثبت نشده است.",
  "Go to Model": "رفتن به مدل",
  "Advanced: project engineering model (legacy)": "پیشرفته: مدل مهندسی پروژه (قدیمی)",
  "Advanced: legacy workspace tools": "پیشرفته: ابزارهای قدیمی",
  // Project analysis page (/workspace/analysis)
  "Project analysis": "آنالیز پروژه",
  "Prepare analysis inputs and track analysis runs.": "ورودی‌های تحلیل را آماده کنید و اجراهای تحلیل را دنبال کنید.",
  "Quick analysis of a 3D frame:": "تحلیل سریع قاب سه‌بعدی:",
  "Model page": "صفحهٔ مدل",
  "Model revision": "نسخهٔ مدل", "Current model": "مدل فعلی", Version: "نسخه",
  "Model readiness": "آمادگی مدل", "Select a project to review model readiness.": "برای دیدن آمادگی مدل یک پروژه انتخاب کنید.",
  "Load combinations": "ترکیب‌های بار", combinations: "ترکیب", "load cases": "حالت بار", "Analysis model": "مدل تحلیل",
  "No load combinations defined in the current model.": "در مدل فعلی ترکیب باری تعریف نشده است.",
  "Load combination summary will appear here.": "خلاصهٔ ترکیب‌های بار اینجا نمایش داده می‌شود.",
  "Run analysis": "اجرای تحلیل", "Analysis type": "نوع تحلیل",
  "Static analysis": "تحلیل استاتیکی", "Modal analysis": "تحلیل مودال", "Drift review": "بررسی تغییرمکان نسبی",
  "Lateral drift review": "بررسی تغییرمکان جانبی نسبی",
  "The platform prepares deterministic model inputs and records the run. Forces, displacements, and modal results are not generated until a solver adapter is connected.":
    "پلتفرم ورودی‌های قطعی مدل را آماده و اجرا را ثبت می‌کند. تا زمانی که حل‌گر متصل نشود، نیروها، تغییرمکان‌ها و نتایج مودال تولید نمی‌شوند.",
  "This page does not read a prompt. To analyse a described 3D frame, send it in the Chat or build it on the Model page: it runs the built-in 3D frame solver and shows the result card.":
    "این صفحه متن درخواست را نمی‌خواند. برای تحلیل یک قاب سه‌بعدی توصیف‌شده، آن را در گفتگو بفرستید یا در صفحهٔ مدل بسازید؛ حل‌گر داخلی قاب سه‌بعدی اجرا می‌شود و کارت نتیجه نمایش داده می‌شود.",
  "Latest run result": "نتیجهٔ آخرین اجرا",
  "No engineering analysis results were generated in this run.": "در این اجرا نتیجهٔ تحلیل مهندسی تولید نشد.",
  "Run history": "تاریخچهٔ اجراها",
  "No analysis runs yet. Check readiness above, then start a run.": "هنوز تحلیلی اجرا نشده است. آمادگی مدل را بالا ببینید و سپس اجرا کنید.",
  "Failed to load analysis workspace": "بارگذاری صفحهٔ تحلیل ناموفق بود", "Analysis failed": "تحلیل ناموفق بود",
  Queued: "در صف", Running: "در حال اجرا", Completed: "تکمیل شد", "Completed with warnings": "تکمیل شد با هشدار", Failed: "ناموفق",
  "Not available yet": "هنوز در دسترس نیست", "Solver required": "نیازمند حل‌گر", "Model not ready": "مدل آماده نیست",
  "Connect ETABS, SAP2000, SAFE, or another solver to produce results": "برای تولید نتایج، ETABS، SAP2000، SAFE یا حل‌گر دیگری را متصل کنید",
  "Complete the engineering model before running analysis": "پیش از اجرای تحلیل، مدل مهندسی را کامل کنید",
  "This analysis type is not supported yet": "این نوع تحلیل هنوز پشتیبانی نمی‌شود",
  "Preparing analysis inputs": "در حال آماده‌سازی ورودی‌های تحلیل",
  Members: "اعضا", Supports: "تکیه‌گاه‌ها", "Load cases": "حالت‌های بار", Levels: "تراز‌ها",
  "Checks passed": "کنترل‌ها موفق", "Review recommended": "بازبینی توصیه می‌شود", "Issues found": "مشکل یافت شد",
  "Uses the built-in 3D frame solver, Standard 2800, Mabhas 9 design and isolated footings — same engine as the chat.":
    "از حل‌گر داخلی قاب سه‌بعدی، استاندارد ۲۸۰۰، طراحی مبحث نهم و پی منفرد استفاده می‌کند — همان موتور گفتگو.",
  Language: "زبان",
  "Sheet": "برگه",
  "View": "نما",
  "Top": "بالا",
  "Isometric": "ایزومتریک",
  "Fit": "نمای کامل",
  "Download": "دانلود",
  "Drag to pan, mouse wheel to zoom.": "برای جابه‌جایی بکشید، برای بزرگنمایی چرخ ماوس.",
  "Project drawings": "نقشه‌های پروژه",
  "Story plans + foundation plan": "پلان طبقات + پلان فونداسیون",
  "3D wireframe": "قاب سه‌بعدی (سیمی)",
  "Downloads": "دانلودها",
  "No drawings yet: analyse a 3D frame in the chat or on the Model page.": "هنوز نقشه‌ای نیست: یک قاب سه‌بعدی را در گفتگو یا صفحهٔ مدل تحلیل کنید.",
  "Calculation report": "گزارش محاسبات",
  "Submit for approval": "ارسال برای تأیید",
  "Rebar detailing drawings": "نقشه‌های آرماتوربندی",
  "Show rebar drawings": "نمایش نقشه آرماتوربندی",
  "Rebar detailing + bar schedule": "آرماتوربندی + جدول میلگرد",
  "Foundation detailing (plan, sections, schedule)": "نقشه فونداسیون (پلان، مقاطع، جدول)",
  "Sent for approval.": "برای تأیید ارسال شد.",
  "Print / PDF": "چاپ / PDF",
  "No report yet: analyse a 3D frame in the chat or on the Model page.": "هنوز گزارشی نیست: یک قاب سه‌بعدی را در گفتگو یا صفحهٔ مدل تحلیل کنید.",
  "No inline preview for this file type.": "پیش‌نمایش این نوع فایل ممکن نیست.",
  "No files uploaded yet.": "هنوز فایلی بارگذاری نشده است.",
  "Upload above, or attach files in the chat.": "از بالا بارگذاری کنید یا در گفتگو پیوست کنید.",
  "Hide preview": "بستن پیش‌نمایش",
  "Preview": "پیش‌نمایش",
  "Create in chat": "ساختن در گفتگو",
  "Example prompt": "نمونهٔ درخواست",
  "No project memory recorded yet.": "هنوز حافظه‌ای برای پروژه ثبت نشده است.",
  "Memory is filled automatically when you analyse a frame or discuss decisions in the project chat.": "حافظه هنگام تحلیل قاب یا بحث دربارهٔ تصمیم‌ها در گفتگوی پروژه به‌طور خودکار پر می‌شود.",
  "Preparing…": "در حال آماده‌سازی…",
  "All": "همه",
 "Open project chat": "گفتگوی پروژه", Details: "جزئیات",
};

export function makeUiT(lang: Frame3dLang): (key: string) => string {
  const base = makeT(lang);
  return (key: string) => (lang === "fa" ? UI_FA[key] ?? base(key) : key);
}
