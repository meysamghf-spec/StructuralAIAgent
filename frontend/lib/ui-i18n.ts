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
  Chat: "گفتگو", Projects: "پروژه‌ها", Model: "مدل", Files: "فایل‌ها", Memory: "حافظه", Learning: "یادگیری",
  Assistants: "دستیارها", "Assistant Builder": "سازندهٔ دستیار", Approvals: "تأییدها", Analysis: "تحلیل",
  Results: "نتایج", Design: "طراحی", Optimization: "بهینه‌سازی", Integrations: "اتصال نرم‌افزارها", CAD: "نقشه (CAD)",
  Validation: "اعتبارسنجی", Reports: "گزارش‌ها", Traceability: "ردیابی", Upgrades: "ارتقا", "AI Assistant": "دستیار هوشمند",
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
  "No 3D frame result yet. Build one on the Model page or describe a frame in the chat.":
    "هنوز نتیجهٔ قاب سه‌بعدی وجود ندارد. در صفحهٔ مدل یک قاب بسازید یا آن را در گفتگو توصیف کنید.",
  "No chat frame found for this project yet.": "هنوز قابی در گفتگوی این پروژه ثبت نشده است.",
  "Go to Model": "رفتن به مدل", "Rerun with saved model": "اجرای دوباره با مدل ذخیره‌شده",
  "Advanced: project engineering model (legacy)": "پیشرفته: مدل مهندسی پروژه (قدیمی)",
  "Advanced: legacy workspace tools": "پیشرفته: ابزارهای قدیمی",
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
