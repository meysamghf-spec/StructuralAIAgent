import { assistantContext } from "./assistant-context";
import type { EngineeringAgentType } from "./api";

export type Bi = { en: string; fa: string };

export type AssistantPageInfo = {
  agentType: EngineeringAgentType;
  slug: string;
  description: Bi;
  abilities: { en: string[]; fa: string[] };
  limits: { en: string[]; fa: string[] };
};

const NEEDS_RESULT: Bi = {
  en: "Answers come from the latest analysis of the selected project or chat; with no analysis yet it only guides you.",
  fa: "پاسخ‌ها از آخرین تحلیل پروژهٔ انتخاب‌شده یا همین گفتگو می‌آید؛ بدون تحلیل فقط راهنمایی می‌کند.",
};

/** Honest per-assistant description. Keep in sync with backend/app/application/assistant_chat.py. */
const PAGES: Record<string, Omit<AssistantPageInfo, "agentType" | "slug">> = {
  STRUCTURAL_MODELING_AGENT: {
    description: {
      en: "Builds and summarizes the 3D reinforced-concrete frame model from storeys, bays and heights.",
      fa: "مدل سه‌بعدی قاب بتنی را از تعداد طبقه، دهانه و ارتفاع می‌سازد و خلاصه می‌کند.",
    },
    abilities: {
      en: ["Create a regular RC frame from a short description", "Edit storeys, bays, spans and heights", "Summarize the model (nodes, members, sections)"],
      fa: ["ساخت قاب بتنی منظم از یک توضیح کوتاه", "ویرایش تعداد طبقه، دهانه، طول دهانه و ارتفاع", "خلاصهٔ مدل (گره‌ها، اعضا، مقاطع)"],
    },
    limits: {
      en: ["Only regular rectangular RC frames (storeys × bays); other structural systems are not generated.", NEEDS_RESULT.en],
      fa: ["فقط قاب بتنی منظم مستطیلی (طبقه × دهانه)؛ سیستم‌های سازه‌ای دیگر ساخته نمی‌شود.", NEEDS_RESULT.fa],
    },
  },
  LOAD_ASSESSMENT_AGENT: {
    description: {
      en: "Summarizes gravity and seismic loading and the load combinations used by the analysis.",
      fa: "بارگذاری ثقلی و لرزه‌ای و ترکیب بارهای استفاده‌شده در تحلیل را خلاصه می‌کند.",
    },
    abilities: {
      en: ["Dead / live / roof-live and wall loads", "Seismic weight, coefficient and base shear", "Load combinations"],
      fa: ["بار مرده، زنده، بام و دیوار", "وزن لرزه‌ای، ضریب زلزله و برش پایه", "ترکیب بارها"],
    },
    limits: {
      en: ["Wind, snow and other special loads are not modeled.", NEEDS_RESULT.en],
      fa: ["باد، برف و بارهای ویژهٔ دیگر مدل نمی‌شوند.", NEEDS_RESULT.fa],
    },
  },
  ANALYSIS_AGENT: {
    description: {
      en: "Reviews the structural analysis: equilibrium, drift, base shear, period and member maxima.",
      fa: "تحلیل سازه را بازبینی می‌کند: تعادل، دریفت، برش پایه، پریود و بیشینهٔ نیروی اعضا.",
    },
    abilities: {
      en: ["Drift and base-shear checks", "Modal period vs empirical period", "Beam / column maxima", "P-Δ status"],
      fa: ["کنترل دریفت و برش پایه", "پریود مودال در برابر تجربی", "بیشینهٔ نیرو در تیر و ستون", "وضعیت اثر P-Δ"],
    },
    limits: {
      en: ["Linear frame analysis only; no nonlinear, shell or foundation-soil analysis.", NEEDS_RESULT.en],
      fa: ["فقط تحلیل خطی قاب؛ تحلیل غیرخطی، پوسته‌ای یا خاک-پی انجام نمی‌شود.", NEEDS_RESULT.fa],
    },
  },
  CONCRETE_DESIGN_AGENT: {
    description: {
      en: "Summarizes the reinforced-concrete member design to Mabhas 9.",
      fa: "طراحی اعضای بتن‌آرمه طبق مبحث نهم را خلاصه می‌کند.",
    },
    abilities: {
      en: ["Beam and column group D/C ratios", "Strong-column / weak-beam check", "Foundation status when available"],
      fa: ["نسبت D/C گروه‌های تیر و ستون", "کنترل ستون قوی–تیر ضعیف", "وضعیت پی در صورت وجود"],
    },
    limits: {
      en: ["Reports a design only after it has been run (say \"design per Mabhas 9\").", "Slab design and detailing sheets are not produced here."],
      fa: ["فقط پس از اجرای طراحی گزارش می‌دهد (بنویسید «طبق مبحث نهم طراحی کن»).", "طراحی دال و نقشهٔ جزئیات در اینجا تولید نمی‌شود."],
    },
  },
  STEEL_DESIGN_AGENT: {
    description: {
      en: "Elastic analysis of a single steel beam: reactions, bending moment, shear and deflection.",
      fa: "تحلیل الاستیک یک تیر فولادی تکی: واکنش‌ها، لنگر خمشی، برش و خیز.",
    },
    abilities: {
      en: ["Simply supported, cantilever and two-span beams", "Uniform and midspan point loads", "Moment / shear diagrams and deflection"],
      fa: ["تیر ساده، کنسول و دو دهانه", "بار گسترده و بار متمرکز وسط دهانه", "نمودار لنگر و برش و خیز"],
    },
    limits: {
      en: [
        "Not a steel code check: no section capacity (AISC 360 / Mabhas 10) result is produced from chat.",
        "The section is an assumed default (IPE 300-like) unless stated; connections and steel-frame design are not available yet.",
      ],
      fa: [
        "کنترل آیین‌نامه‌ای فولاد نیست: ظرفیت مقطع (AISC 360 / مبحث دهم) از چت محاسبه نمی‌شود.",
        "مقطع، مگر ذکر شود، پیش‌فرض فرضی (مشابه IPE 300) است؛ اتصالات و طراحی قاب فولادی هنوز موجود نیست.",
      ],
    },
  },
  SEISMIC_AGENT: {
    description: {
      en: "Shows the Standard 2800 seismic parameters, base shear, storey forces and drift check.",
      fa: "پارامترهای لرزه‌ای استاندارد ۲۸۰۰، برش پایه، نیروی طبقات و کنترل دریفت را نشان می‌دهد.",
    },
    abilities: {
      en: ["Zone, soil, importance and system parameters", "Base shear and storey force distribution", "Drift check"],
      fa: ["پارامترهای پهنه، خاک، اهمیت و سیستم", "برش پایه و توزیع نیرو در طبقات", "کنترل دریفت"],
    },
    limits: {
      en: ["Equivalent-static method only; no response-spectrum or time-history results.", NEEDS_RESULT.en],
      fa: ["فقط روش استاتیکی معادل؛ طیفی یا تاریخچهٔ زمانی ارائه نمی‌شود.", NEEDS_RESULT.fa],
    },
  },
  VALIDATION_AGENT: {
    description: {
      en: "Lists passed and failed checks and warnings from the latest analysis and design.",
      fa: "کنترل‌های موفق و ناموفق و هشدارهای آخرین تحلیل و طراحی را فهرست می‌کند.",
    },
    abilities: {
      en: ["Drift, base shear, Mabhas 9, SCWB, foundation status", "All stored warnings"],
      fa: ["دریفت، برش پایه، مبحث نهم، SCWB و وضعیت پی", "همهٔ هشدارهای ثبت‌شده"],
    },
    limits: {
      en: ["Computational validation only; final approval rests with the responsible engineer.", NEEDS_RESULT.en],
      fa: ["فقط اعتبارسنجی محاسباتی است؛ تأیید نهایی با مهندس مسئول است.", NEEDS_RESULT.fa],
    },
  },
  CAD_AGENT: {
    description: {
      en: "Explains which drawings can be produced from the model and points you to the CAD page.",
      fa: "توضیح می‌دهد از مدل چه نقشه‌هایی ساخته می‌شود و شما را به صفحهٔ CAD می‌برد.",
    },
    abilities: {
      en: ["Structural drawing set (plans, sections, schedules)", "Reinforcement schedules"],
      fa: ["مجموعه نقشه‌های سازه (پلان، مقطع، جدول)", "جدول آرماتور"],
    },
    limits: {
      en: ["Needs a completed model and design; drawings are generated files, not edited here.", "Drawing sheets must be reviewed by an engineer before use."],
      fa: ["به مدل و طراحی کامل نیاز دارد؛ نقشه‌ها فایل تولیدشده‌اند و اینجا ویرایش نمی‌شوند.", "نقشه‌ها پیش از استفاده باید توسط مهندس بازبینی شوند."],
    },
  },
  REPORTING_AGENT: {
    description: {
      en: "Summarizes runs for the engineering report and lists what is ready to report.",
      fa: "اجراها را برای گزارش مهندسی خلاصه می‌کند و آنچه آمادهٔ گزارش است را فهرست می‌کند.",
    },
    abilities: {
      en: ["Report summary of the latest run", "List of runs available for a report"],
      fa: ["خلاصهٔ گزارش آخرین اجرا", "فهرست اجراهای آمادهٔ گزارش"],
    },
    limits: {
      en: ["The full report file is downloaded from the Reports page.", NEEDS_RESULT.en],
      fa: ["فایل کامل گزارش از صفحهٔ گزارش‌ها دریافت می‌شود.", NEEDS_RESULT.fa],
    },
  },
  DOCUMENT_INTERPRETATION_AGENT: {
    description: {
      en: "Interprets attached PDF, Excel, DXF and image files into engineering inputs.",
      fa: "فایل‌های پیوست PDF، اکسل، DXF و تصویر را به ورودی مهندسی تفسیر می‌کند.",
    },
    abilities: {
      en: ["Read attached specs and drawings", "Extract requirements for review"],
      fa: ["خواندن مشخصات و نقشه‌های پیوست", "استخراج الزامات برای بازبینی"],
    },
    limits: {
      en: ["Extraction can be incomplete; check extracted values before using them.", "Attach files in the full chat; this page chat is text only."],
      fa: ["استخراج ممکن است ناقص باشد؛ مقادیر را قبل از استفاده بررسی کنید.", "فایل‌ها را در چت کامل پیوست کنید؛ چت این صفحه فقط متنی است."],
    },
  },
  OPTIMIZATION_AGENT: {
    description: {
      en: "Optimizes frame member sections for cost and lists missing prerequisites.",
      fa: "مقاطع اعضای قاب را برای کاهش هزینه بهینه می‌کند و پیش‌نیازهای کم را فهرست می‌کند.",
    },
    abilities: {
      en: ["Section optimization for cost", "Prerequisite checklist", "Before / after cost comparison"],
      fa: ["بهینه‌سازی مقاطع برای هزینه", "فهرست پیش‌نیازها", "مقایسهٔ هزینه قبل و بعد"],
    },
    limits: {
      en: ["Needs a model, analysis and design; missing pieces are completed with stated defaults.", "Optimizes RC frame sections only."],
      fa: ["به مدل، تحلیل و طراحی نیاز دارد؛ موارد کم با پیش‌فرض‌های اعلام‌شده تکمیل می‌شود.", "فقط مقاطع قاب بتنی را بهینه می‌کند."],
    },
  },
  STRUCTURAL_ENGINEERING_AGENT: {
    description: {
      en: "Runs the project workflow from the brief through analysis, design checks and reporting.",
      fa: "جریان کار پروژه را از شرح مسئله تا تحلیل، کنترل‌های طراحی و گزارش اجرا می‌کند.",
    },
    abilities: {
      en: ["Analyze and design a described RC frame", "Explain the platform and next steps"],
      fa: ["تحلیل و طراحی قاب بتنی توصیف‌شده", "توضیح پلتفرم و گام‌های بعدی"],
    },
    limits: {
      en: ["Covers what the other assistants cover; steel frames and unsupported systems are not designed.", "It does not replace review by the responsible engineer."],
      fa: ["همان حوزهٔ سایر دستیارها را پوشش می‌دهد؛ قاب فولادی و سیستم‌های پشتیبانی‌نشده طراحی نمی‌شوند.", "جایگزین بازبینی مهندس مسئول نیست."],
    },
  },
};

export function assistantSlug(agentType: string): string {
  return agentType.toLowerCase().replace(/_agent$/, "").replace(/_/g, "-");
}

/** Accepts the short slug ("steel-design") or the raw type ("STEEL_DESIGN_AGENT"). */
export function agentTypeFromSlug(slug: string | null | undefined): EngineeringAgentType | null {
  if (!slug) return null;
  const clean = decodeURIComponent(slug).toLowerCase();
  for (const type of Object.keys(PAGES)) {
    if (assistantSlug(type) === clean || type.toLowerCase() === clean) return type as EngineeringAgentType;
  }
  return null;
}

export function assistantPageHref(agentType: string, projectId?: string | null): string {
  const base = `/workspace/agents/${assistantSlug(agentType)}`;
  return projectId ? `${base}?project=${encodeURIComponent(projectId)}` : base;
}

export function assistantPageInfo(agentType: string | null | undefined): AssistantPageInfo | null {
  if (!agentType) return null;
  const type = agentType.toUpperCase();
  const page = PAGES[type];
  if (!page || !assistantContext(type)) return null;
  return { agentType: type as EngineeringAgentType, slug: assistantSlug(type), ...page };
}

export const ASSISTANT_PAGE_TYPES = Object.keys(PAGES) as EngineeringAgentType[];
