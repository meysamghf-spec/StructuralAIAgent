// Pure helpers for the results-only Analysis page (KPIs, chart series, model chips). No UI, no network.
import type { Frame3dResults } from "./chat-types";

export type DriftStatus = "pass" | "review" | "reference" | "none";

export type AnalysisKpis = {
  /** Largest cumulative lateral displacement at the roof (Σ elastic storey drifts), mm. */
  maxDisplacementMm: number | null;
  maxDisplacementDir: string | null;
  /** Largest amplified (design) drift ratio, %. */
  maxDriftPct: number | null;
  driftLimitPct: number | null;
  driftStatus: DriftStatus;
  fundamentalPeriodS: number | null;
  baseShearKn: number | null;
  totalMassT: number | null;
};

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Roof displacement per direction = sum of the elastic storey drifts of that direction. */
export function roofDisplacements(drift: Frame3dResults["drift"]): Array<{ direction: string; mm: number }> {
  const acc = new Map<string, number>();
  for (const r of drift) {
    const d = num(r.driftElasticMm);
    if (d === null) continue;
    acc.set(r.direction, (acc.get(r.direction) ?? 0) + d);
  }
  return [...acc.entries()].map(([direction, mm]) => ({ direction, mm }));
}

/** Total mass (t) when the result fields carry a mass/weight line; weight in kN is converted with g = 9.81. */
export function findTotalMassT(fields: Frame3dResults["fields"]): number | null {
  for (const f of fields) {
    const label = f.label.toLowerCase();
    const value = Number(String(f.value).replace(/[, ]/g, ""));
    if (!Number.isFinite(value)) continue;
    const unit = (f.unit ?? "").toLowerCase();
    if (/mass|جرم/.test(label)) return unit.startsWith("kg") ? value / 1000 : value;
    if (/weight|وزن/.test(label) && unit === "kn") return value / 9.81;
  }
  return null;
}

export function computeKpis(r: Frame3dResults): AnalysisKpis {
  const roofs = roofDisplacements(r.drift);
  const maxRoof = roofs.reduce<{ direction: string; mm: number } | null>((m, x) => (!m || x.mm > m.mm ? x : m), null);
  const ratios = r.drift.map((d) => num(d.ratioAmplifiedPct)).filter((x): x is number => x !== null);
  const maxDriftPct = ratios.length ? Math.max(...ratios) : null;
  const limit = r.driftReferenceLimitPct;
  let driftStatus: DriftStatus = "none";
  if (maxDriftPct !== null && limit !== null) {
    driftStatus = r.driftCheck ? (maxDriftPct <= limit ? "pass" : "review") : "reference";
  }
  const shears = r.storeyLateral.map((s) => num(s.shearKn)).filter((x): x is number => x !== null);
  return {
    maxDisplacementMm: maxRoof ? maxRoof.mm : null,
    maxDisplacementDir: maxRoof ? maxRoof.direction : null,
    maxDriftPct,
    driftLimitPct: limit,
    driftStatus,
    fundamentalPeriodS: r.modal?.fundamentalPeriodS ?? r.modal?.modes?.[0]?.periodS ?? null,
    baseShearKn: shears.length ? Math.max(...shears) : null,
    totalMassT: findTotalMassT(r.fields),
  };
}

/** Per-storey bar-chart series (one list per direction), highest storey last. */
export function driftSeries(drift: Frame3dResults["drift"]): Record<string, Array<{ storey: number; pct: number }>> {
  const out: Record<string, Array<{ storey: number; pct: number }>> = {};
  for (const r of drift) {
    const pct = num(r.ratioAmplifiedPct) ?? num(r.ratioElasticPct);
    if (pct === null) continue;
    (out[r.direction] ??= []).push({ storey: r.storey, pct });
  }
  for (const k of Object.keys(out)) out[k].sort((a, b) => a.storey - b.storey);
  return out;
}

/** Model summary chips shown in the banner (read-only; from the run's own inputs). */
export function modelChips(inputs: Record<string, unknown> | null | undefined, lang: "en" | "fa"): string[] {
  if (!inputs) return [];
  const n = (k: string) => num(inputs[k]);
  const chips: string[] = [];
  const fa = lang === "fa";
  if (n("storeys") !== null) chips.push(fa ? `${n("storeys")} طبقه` : `${n("storeys")} storeys`);
  if (n("bays_x") !== null && n("bays_y") !== null) chips.push(fa ? `${n("bays_x")}×${n("bays_y")} دهانه` : `${n("bays_x")}×${n("bays_y")} bays`);
  if (n("bay_x_m") !== null && n("bay_y_m") !== null) chips.push(fa ? `دهانه ${n("bay_x_m")}×${n("bay_y_m")} متر` : `spans ${n("bay_x_m")}×${n("bay_y_m")} m`);
  if (n("storey_height_m") !== null) chips.push(fa ? `ارتفاع طبقه ${n("storey_height_m")} متر` : `storey h ${n("storey_height_m")} m`);
  return chips;
}

export function fmtNum(v: number | null, digits: number): string {
  return v === null ? "—" : v.toFixed(digits);
}
