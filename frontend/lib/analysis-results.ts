// View-model for the /workspace/analysis page. Pure functions over the payload returned by POST /api/v1/frame3d/run
// (the same built-in 3D frame solver the chat and Model page use). Nothing is computed or invented here: every number is
// taken from the engine payload; missing values stay null and the UI shows "—".
import { mapFrame3dResults } from "./chat-mappers";
import type { Frame3dResults } from "./chat-types";
import { FRAME_FORM_FIELDS } from "./frame3d-store";
import { makeUiT } from "./ui-i18n";
import type { Frame3dLang } from "./frame3d-i18n";

type Rec = Record<string, unknown>;

function rec(v: unknown): Rec {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Rec) : {};
}
function recs(v: unknown): Rec[] {
  return Array.isArray(v) ? v.filter((x): x is Rec => !!x && typeof x === "object") : [];
}
function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return null;
}
function strs(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

/** Inputs the solver needs before it can run at all (same rule as the backend's missing_inputs). */
export const REQUIRED_MODEL_INPUTS = ["storeys", "bays_x", "bays_y"] as const;

export function missingModelInputs(inputs: Record<string, unknown> | null): string[] {
  if (!inputs) return [...REQUIRED_MODEL_INPUTS];
  return REQUIRED_MODEL_INPUTS.filter((k) => {
    const v = num(inputs[k]);
    return v === null || v < 1;
  });
}

export function inputLabel(key: string): string {
  return FRAME_FORM_FIELDS.find((f) => f.key === key)?.label ?? key;
}

export type DriftState = "pass" | "review" | "reference" | "none";

export type StoreyRow = {
  storey: number;
  /** max |lateral displacement| at this level (elastic, mm) per direction */
  displacementMm: Record<string, number | null>;
  /** amplified inelastic drift ratio (%) per direction */
  driftPct: Record<string, number | null>;
  driftElasticMm: Record<string, number | null>;
  forceKn: number | null;
  shearKn: number | null;
};

export type MemberRow = { id: string; kind: "beam" | "column"; storey: number | null; position: string | null; a: number | null; b: number | null; c: number | null };

export type AnalysisView = {
  completed: boolean;
  status: string;
  message: string | null;
  code: string | null;
  seismicCode: string | null;
  disclaimer: string | null;
  directions: string[];
  storeys: StoreyRow[];
  maxDisplacement: { mm: number; direction: string; storey: number } | null;
  maxDrift: { pct: number; direction: string; storey: number } | null;
  driftLimitPct: number | null;
  driftState: DriftState;
  fundamentalPeriodS: number | null;
  modes: Array<{ mode: number; periodS: number | null; massXPct: number | null; massYPct: number | null; massRzPct: number | null; cumXPct: number | null; cumYPct: number | null }>;
  modesFor90: Record<string, number> | null;
  baseShear: { vKn: number | null; c: number | null; weightKn: number | null; status: string | null } | null;
  spectrum: Array<{ direction: string; vDynamicKn: number | null; vStaticKn: number | null; scaleFactor: number | null }>;
  pDelta: { status: string | null; thetaMax: Record<string, number> | null; thetaLimit: number | null } | null;
  storeyMember: Array<{ storey: number; beamMNegKnM: number | null; beamMPosKnM: number | null; beamVKn: number | null; columnPKn: number | null; columnMKnM: number | null }>;
  members: MemberRow[];
  missing: string[];
  assumptions: string[];
  warnings: string[];
  inputs: Record<string, unknown> | null;
};

export function summarizeAnalysis(raw: unknown): AnalysisView | null {
  const mapped: Frame3dResults | null = mapFrame3dResults(raw);
  if (!mapped) return null;
  const data = rec(raw);
  const completed = mapped.status === "completed";

  const driftRaw = recs(data.drift);
  const directions = Array.from(new Set(driftRaw.map((d) => String(d.direction ?? "")).filter(Boolean)));
  const byStorey = new Map<number, StoreyRow>();
  const row = (k: number): StoreyRow => {
    let r = byStorey.get(k);
    if (!r) {
      r = { storey: k, displacementMm: {}, driftPct: {}, driftElasticMm: {}, forceKn: null, shearKn: null };
      byStorey.set(k, r);
    }
    return r;
  };
  for (const d of driftRaw) {
    const dir = String(d.direction ?? "");
    const r = row(Number(d.storey ?? 0));
    r.displacementMm[dir] = num(d.u_max_mm);
    r.driftPct[dir] = num(d.ratio_amplified_pct);
    r.driftElasticMm[dir] = num(d.drift_elastic_mm);
  }
  for (const s of mapped.storeyLateral) {
    const r = row(s.storey);
    r.forceKn = s.forceKn;
    r.shearKn = s.shearKn;
  }
  const storeys = [...byStorey.values()].sort((a, b) => a.storey - b.storey);

  let maxDisplacement: AnalysisView["maxDisplacement"] = null;
  let maxDrift: AnalysisView["maxDrift"] = null;
  for (const s of storeys) {
    for (const dir of Object.keys(s.displacementMm)) {
      const u = s.displacementMm[dir];
      if (u !== null && (maxDisplacement === null || Math.abs(u) > maxDisplacement.mm)) maxDisplacement = { mm: Math.abs(u), direction: dir, storey: s.storey };
      const p = s.driftPct[dir];
      if (p !== null && (maxDrift === null || p > maxDrift.pct)) maxDrift = { pct: p, direction: dir, storey: s.storey };
    }
  }

  const limit = mapped.driftReferenceLimitPct;
  let driftState: DriftState = "none";
  if (maxDrift) {
    if (mapped.driftCheck === "PASS") driftState = "pass";
    else if (mapped.driftCheck === "FAIL") driftState = "review";
    else driftState = limit !== null ? "reference" : "none";
  }

  const modalRaw = rec(data.modal);
  const modes = recs(modalRaw.modes).map((m) => ({
    mode: Number(m.mode ?? 0),
    periodS: num(m.T_s),
    massXPct: num(m.mass_x_pct),
    massYPct: num(m.mass_y_pct),
    massRzPct: num(m.mass_rz_pct),
    cumXPct: num(m.cum_x_pct),
    cumYPct: num(m.cum_y_pct),
  }));
  const m90 = rec(modalRaw.modes_for_90pct);
  const modesFor90 = Object.keys(m90).length
    ? Object.fromEntries(Object.entries(m90).flatMap(([k, v]) => (num(v) !== null ? [[k, num(v) as number]] : [])))
    : null;

  const bsRaw = rec(data.base_shear_check);
  const baseShear = Object.keys(bsRaw).length
    ? { vKn: num(bsRaw.V_expected_kn), c: num(bsRaw.C), weightKn: num(bsRaw.W_total_kn), status: typeof bsRaw.status === "string" ? bsRaw.status : null }
    : null;

  const pdRaw = rec(data.p_delta);
  const thetaMaxRaw = rec(pdRaw.theta_max);
  const pDelta = Object.keys(pdRaw).length
    ? {
        status: typeof pdRaw.status === "string" ? pdRaw.status : null,
        thetaMax: Object.keys(thetaMaxRaw).length ? Object.fromEntries(Object.entries(thetaMaxRaw).flatMap(([k, v]) => (num(v) !== null ? [[k, num(v) as number]] : []))) : null,
        thetaLimit: num(pdRaw.theta_limit),
      }
    : null;

  const colByStorey = recs(data.column_forces_by_storey);
  const storeyMember = mapped.storeyForces.map((s) => ({
    storey: s.storey,
    beamMNegKnM: s.beamMNegKnM,
    beamMPosKnM: s.beamMPosKnM,
    beamVKn: s.beamVKn,
    columnPKn: s.columnPKn,
    columnMKnM: num(colByStorey.find((c) => Number(c.storey) === s.storey)?.M_kn_m),
  }));

  const env = rec(data.envelopes);
  const members: MemberRow[] = [
    ...recs(env.beams).map((b) => ({ id: String(b.id ?? ""), kind: "beam" as const, storey: num(b.storey), position: typeof b.position === "string" ? b.position : null, a: num(b.M_neg_kn_m), b: num(b.M_pos_kn_m), c: num(b.V_kn) })),
    ...recs(env.columns).map((c) => ({ id: String(c.id ?? ""), kind: "column" as const, storey: num(c.storey), position: typeof c.position === "string" ? c.position : null, a: num(c.P_kn), b: num(c.M_kn_m), c: null })),
  ];

  return {
    completed,
    status: mapped.status,
    message: mapped.message,
    code: mapped.code,
    seismicCode: mapped.seismicCode,
    disclaimer: mapped.disclaimer,
    directions,
    storeys,
    maxDisplacement,
    maxDrift,
    driftLimitPct: limit,
    driftState,
    fundamentalPeriodS: mapped.modal?.fundamentalPeriodS ?? null,
    modes,
    modesFor90,
    baseShear,
    spectrum: (mapped.modal?.spectrum ?? []).map((s) => ({ direction: s.direction, vDynamicKn: s.vDynamicKn, vStaticKn: s.vStaticKn, scaleFactor: s.scaleFactor })),
    pDelta,
    storeyMember,
    members,
    missing: mapped.missing,
    assumptions: mapped.assumptions,
    warnings: mapped.warnings,
    inputs: mapped.inputs,
  };
}

/** Run timestamp is not part of the engine payload; the page records it next to the saved payload when the user runs. */
const RUN_KEY = "sa.analysis.lastRun";
export type LastRun = { at: string; ok: boolean };

export function saveLastRun(projectId: string | null, run: LastRun): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(`${RUN_KEY}.${projectId || "none"}`, JSON.stringify(run));
  } catch {
    /* storage unavailable */
  }
}

export function loadLastRun(projectId: string | null): LastRun | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(`${RUN_KEY}.${projectId || "none"}`);
    const v = raw ? (JSON.parse(raw) as LastRun) : null;
    return v && typeof v.at === "string" ? v : null;
  } catch {
    return null;
  }
}

export function formatNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: digits, useGrouping: false });
}

export function unitSystemLabel(): string {
  // Units are fixed by the engine output: forces kN, moments kN·m, lengths m / displacements mm, periods s, drift %.
  return "kN · m · mm · s";
}

// ---- translations (kept out of ui-i18n.ts to avoid merge conflicts with stacked PRs) ----
export const AN_FA: Record<string, string> = {
  "Analysis": "آنالیز",
  "Project analysis": "آنالیز پروژه",
  "Analyze": "آنالیز",
  "Analyzing…": "در حال آنالیز…",
  "Analyze the current model and show its results here.": "مدل فعلی را آنالیز می‌کند و نتایج را همین‌جا نشان می‌دهد.",
  "Results of the built-in 3D frame solver for the current model of this project.": "نتایج حل‌گر داخلی قاب سه‌بعدی برای مدل فعلی این پروژه.",
  "Project": "پروژه",
  "Status": "وضعیت",
  "Last analysis": "آخرین آنالیز",
  "Date not recorded": "تاریخ ثبت نشده",
  "Design code": "آیین‌نامه",
  "Seismic code": "آیین‌نامه زلزله",
  "Units": "واحدها",
  "Completed": "تکمیل شد",
  "Not completed": "ناتمام",
  "Analysis completed": "آنالیز تکمیل شد",
  "Analysis succeeded. The results below are updated.": "آنالیز با موفقیت انجام شد. نتایج زیر به‌روز شد.",
  "Analysis failed": "آنالیز ناموفق بود",
  "The previous results are still shown below.": "نتایج قبلی همچنان در زیر نمایش داده می‌شوند.",
  "No analysis results yet": "هنوز نتیجهٔ آنالیزی وجود ندارد",
  "Press Analyze to run the solver on the current model. Results will appear here.": "برای اجرای حل‌گر روی مدل فعلی، «آنالیز» را بزنید. نتایج اینجا نمایش داده می‌شود.",
  "Analysis is disabled": "آنالیز در دسترس نیست",
  "Select a project first.": "ابتدا یک پروژه انتخاب کنید.",
  "No model saved for this project yet. Build one on the Model page or describe it in the chat.": "هنوز مدلی برای این پروژه ذخیره نشده است. آن را در صفحهٔ مدل بسازید یا در گفتگو توصیف کنید.",
  "Required inputs are missing:": "ورودی‌های لازم کامل نیستند:",
  "Complete them on the Model page.": "آن‌ها را در صفحهٔ مدل کامل کنید.",
  "Model page": "صفحهٔ مدل",
  "Chat": "گفتگو",
  "Current model": "مدل فعلی",
  "storeys": "طبقه",
  "bays": "دهانه",
  "Max displacement": "بیشینهٔ تغییرمکان",
  "Max story drift": "بیشینهٔ دریفت طبقه",
  "Fundamental period": "پریود اصلی",
  "Base shear": "برش پایه",
  "Pass": "قبول",
  "Needs review": "نیازمند بازبینی",
  "Reference only": "فقط مرجع",
  "limit": "حد مجاز",
  "storey": "طبقه",
  "dir": "جهت",
  "Elastic lateral displacement of the highest level.": "تغییرمکان جانبی ارتجاعی بالاترین تراز.",
  "Amplified (inelastic) drift ratio from the design-force analysis.": "نسبت دریفت بزرگ‌نمایی‌شده (غیرارتجاعی) از آنالیز با نیروی طراحی.",
  "Not computed for this model": "برای این مدل محاسبه نشده است",
  "Drift and displacement per storey": "دریفت و تغییرمکان در هر طبقه",
  "Story drift ratio (%)": "نسبت دریفت طبقه (٪)",
  "Lateral displacement (mm)": "تغییرمکان جانبی (mm)",
  "Storey": "طبقه",
  "Direction": "جهت",
  "Displacement (mm)": "تغییرمکان (mm)",
  "Drift Δ elastic (mm)": "دریفت ارتجاعی Δ (mm)",
  "Drift ratio (%)": "نسبت دریفت (٪)",
  "Drift limit": "حد دریفت",
  "Modal periods": "پریودهای مودال",
  "Mode": "مود",
  "Period T (s)": "پریود T (s)",
  "Mass X (%)": "جرم X (٪)",
  "Mass Y (%)": "جرم Y (٪)",
  "Mass Rz (%)": "جرم Rz (٪)",
  "Cumulative X (%)": "تجمعی X (٪)",
  "Cumulative Y (%)": "تجمعی Y (٪)",
  "Modes needed for 90% mass": "مودهای لازم برای ۹۰٪ جرم",
  "Modal analysis was not run for this model.": "برای این مدل آنالیز مودال اجرا نشده است.",
  "Base shear and storey forces": "برش پایه و نیروهای طبقات",
  "Seismic weight W": "وزن لرزه‌ای W",
  "Seismic coefficient C": "ضریب زلزله C",
  "Base shear V": "برش پایه V",
  "Equilibrium check": "کنترل تعادل",
  "Storey force F (kN)": "نیروی طبقه F (kN)",
  "Storey shear V (kN)": "برش طبقه V (kN)",
  "Dynamic vs static base shear": "برش پایه دینامیکی در برابر استاتیکی",
  "V dynamic (kN)": "V دینامیکی (kN)",
  "V static (kN)": "V استاتیکی (kN)",
  "Scale factor": "ضریب مقیاس",
  "Member forces": "نیروهای اعضا",
  "Envelope per storey": "پوش در هر طبقه",
  "Beam M⁻ (kN·m)": "تیر M⁻ (kN·m)",
  "Beam M⁺ (kN·m)": "تیر M⁺ (kN·m)",
  "Beam V (kN)": "تیر V (kN)",
  "Column P (kN)": "ستون P (kN)",
  "Column M (kN·m)": "ستون M (kN·m)",
  "All members": "همهٔ اعضا",
  "members": "عضو",
  "Member": "عضو",
  "Type": "نوع",
  "Position": "موقعیت",
  "Beam": "تیر",
  "Column": "ستون",
  "Stability (P-Δ)": "پایداری (P-Δ)",
  "Max stability index θ": "بیشینهٔ شاخص پایداری θ",
  "Assumptions and limitations": "فرض‌ها و محدودیت‌ها",
  "Warnings": "هشدارها",
  "Assumptions": "فرض‌ها",
  "Limits of this page: results come from the built-in solver; they are not an approval. A responsible engineer must review them.": "محدودیت: نتایج از حل‌گر داخلی می‌آیند و تأیید مهندسی نیستند؛ مهندس مسئول باید آن‌ها را بازبینی کند.",
  "Results are stored in this browser for the project. They are not yet a server-side approved run.": "نتایج برای این پروژه در همین مرورگر ذخیره می‌شوند و هنوز اجرای تأییدشدهٔ سمت سرور نیستند.",
  "Analysis run failed": "اجرای آنالیز ناموفق بود",
  "Model not analysed": "مدل آنالیز نشده است",
  "Model saved, not analysed yet": "مدل ذخیره شده، هنوز آنالیز نشده",
};

export function makeAnalysisT(lang: Frame3dLang): (key: string) => string {
  const base = makeUiT(lang);
  return (key: string) => (lang === "fa" ? AN_FA[key] ?? base(key) : key);
}
