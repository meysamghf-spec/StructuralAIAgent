/** Display helpers for Mabhas 9 design tables (chat card + Design page). */

export type DcDisplay = { text: string; title: string | undefined; ng: boolean; over: boolean };

/** Backend sends ±999 when a D/C cannot be computed (section cannot develop Mu). */
export const DC_SENTINEL = 999;
export const DC_CAP = 10;

export function toNumber(v: unknown): number | null {
  const n = typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" ? Number.parseFloat(v) : NaN;
  return Number.isFinite(n) ? n : null;
}

export function dcDisplay(v: unknown, digits = 3): DcDisplay {
  const n = toNumber(v);
  if (n === null) return { text: "—", title: undefined, ng: false, over: false };
  if (Math.abs(n) >= DC_SENTINEL) {
    return { text: "NG", title: "D/C not computable: the section cannot resist the force — enlarge it · نسبت تنش قابل محاسبه نیست: مقطع جوابگو نیست، مقطع را بزرگ کنید", ng: true, over: true };
  }
  if (n > DC_CAP) {
    return { text: `>${DC_CAP}`, title: `D/C = ${n.toFixed(2)} (> ${DC_CAP}) — NG, enlarge the section · نسبت تنش ${n.toFixed(2)} — مقطع را بزرگ کنید`, ng: true, over: true };
  }
  return { text: n.toFixed(digits), title: undefined, ng: false, over: n > 1 + 1e-9 };
}

export type RebarBasis = "DESIGN" | "MAX_FEASIBLE" | "MINIMUM";

export function rebarBasisTag(basis: unknown): { short: string; title: string } | null {
  if (basis === "MAX_FEASIBLE") {
    return { short: "NG·max", title: "NG: the most reinforcement the section can hold is shown · غیرقابل‌قبول: حداکثر آرماتور قابل‌جاگذاری نمایش داده شده" };
  }
  if (basis === "MINIMUM") {
    return { short: "NG·min", title: "NG: Mabhas 9 minimum reinforcement is shown · غیرقابل‌قبول: حداقل آرماتور مبحث ۹ نمایش داده شده" };
  }
  return null;
}

export const DESIGN_LEGEND: Array<{ en: string; fa: string }> = [
  { en: "Mu⁻ / Mu⁺: design moment at support / span (kN·m)", fa: "Mu⁻ / Mu⁺: لنگر طراحی تکیه‌گاه / وسط دهانه (kN·m)" },
  { en: "Vu: design shear (kN); Pu: axial force (kN)", fa: "Vu: برش طراحی (kN)؛ Pu: نیروی محوری (kN)" },
  { en: "D/C: demand / capacity, ≤ 1 passes", fa: "D/C: نسبت تقاضا به ظرفیت، ≤ ۱ قبول" },
  { en: ">10 or NG: the section is far too small — enlarge it (hover for the value)", fa: ">10 یا NG: مقطع بسیار کوچک است — مقطع را بزرگ کنید (برای مقدار، نشانگر را نگه دارید)" },
  { en: "NG·max / NG·min: reinforcement shown is the most the section holds / the Mabhas 9 minimum", fa: "NG·max / NG·min: آرماتور نمایش‌داده‌شده حداکثر قابل‌جاگذاری / حداقل مبحث ۹ است" },
  { en: "Suggested: a section size that passes for this member (re-run the analysis to confirm)", fa: "پیشنهادی: ابعاد مقطعی که برای این عضو جوابگوست (برای تأیید، تحلیل را دوباره اجرا کنید)" },
];
