import { FRAME_LIMITS } from "@/lib/frame3d-limits";
// Any-length-unit -> metres helper for the Model form and inline missing-input forms (mirrors backend length_units.py).
export const LENGTH_UNITS = ["m", "cm", "mm", "ft"] as const;
export type LengthUnit = (typeof LENGTH_UNITS)[number];

const TO_M: Record<LengthUnit, number> = { m: 1, cm: 0.01, mm: 0.001, ft: 0.3048 };

/** Allowed frame span range in metres (same limits as the backend /frame3d/run validation). */
export const SPAN_MIN_M = FRAME_LIMITS.minSpanM;
export const SPAN_MAX_M = FRAME_LIMITS.maxSpanM;

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/** Parse a typed number: Persian/Arabic digits, "," or "٫" as the decimal mark. Blank/invalid -> null. */
export function parseNumber(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : null;
  let s = String(raw).trim();
  if (!s) return null;
  s = s
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)))
    .replace(/[٫,]/g, ".")
    .replace(/[٬\s]/g, "");
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(s)) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export function toMetres(value: number, unit: LengthUnit): number {
  return value * TO_M[unit];
}

export function fromMetres(metres: number, unit: LengthUnit): number {
  return metres / TO_M[unit];
}

/** Trim float noise (6000 mm -> 6, 15 ft -> 4.572). */
export function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

/** Typed value + unit -> metres (or null when blank/invalid). */
export function typedToMetres(raw: string, unit: LengthUnit): number | null {
  const n = parseNumber(raw);
  return n === null ? null : round4(toMetres(n, unit));
}

export function spanRangeError(metres: number | null, lang: "en" | "fa"): string | null {
  if (metres === null) return null;
  if (metres >= SPAN_MIN_M && metres <= SPAN_MAX_M) return null;
  return lang === "fa"
    ? `طول دهانه باید بین ${SPAN_MIN_M} تا ${SPAN_MAX_M} متر باشد (الان ${round4(metres)} متر).`
    : `Span must be between ${SPAN_MIN_M} and ${SPAN_MAX_M} m (got ${round4(metres)} m).`;
}
