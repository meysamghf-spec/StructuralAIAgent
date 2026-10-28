"use client";

import { inputLabel, SPAN_KEYS } from "@/lib/input-labels";
import { LENGTH_UNITS, parseNumber, spanRangeError, typedToMetres, type LengthUnit } from "@/lib/length-units";

type Lang = "en" | "fa";
const isSpan = (k: string) => (SPAN_KEYS as readonly string[]).includes(k);

export const PLACEHOLDER: Record<string, string> = {
  storeys: "3", bays_x: "2", bays_y: "2", bay_x_m: "5", bay_y_m: "5",
};

/** Label without the trailing "(m)" — the unit selector next to the input replaces it. */
export function shortLabel(key: string, lang: Lang): string {
  return inputLabel(key, lang).replace(/\s*[(（][^)）]*[)）]\s*$/, "");
}

const MSG = {
  required: { en: "Required — enter a value", fa: "لازم است — یک مقدار وارد کنید" },
  count: { en: "Enter a whole number ≥ 1", fa: "یک عدد صحیح ≥ ۱ وارد کنید" },
  number: { en: "Enter a number", fa: "یک عدد وارد کنید" },
};

/** Validate required geometry values typed in the form (spans converted with their unit). */
export function validateGeometry(
  values: Record<string, string>,
  units: Partial<Record<string, LengthUnit>>,
  lang: Lang,
  keys: readonly string[],
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const k of keys) {
    const raw = (values[k] ?? "").trim();
    if (!raw) {
      errors[k] = MSG.required[lang];
      continue;
    }
    const n = parseNumber(raw);
    if (n === null) {
      errors[k] = MSG.number[lang];
      continue;
    }
    if (isSpan(k)) {
      if (n <= 0) errors[k] = MSG.number[lang];
      else {
        const m = typedToMetres(raw, units[k] ?? "m");
        const e = spanRangeError(m, lang);
        if (e) errors[k] = e;
      }
    } else if (!Number.isInteger(n) || n < 1 || n > 100) {
      errors[k] = MSG.count[lang];
    }
  }
  return errors;
}

type Props = {
  fieldKey: string;
  value: string;
  unit?: LengthUnit;
  lang: Lang;
  error?: string;
  idPrefix?: string;
  onValue: (v: string) => void;
  onUnit?: (u: LengthUnit) => void;
};

/** One required geometry field: friendly label, placeholder (never a hidden default), unit selector + live metres for spans. */
export function GeometryField({ fieldKey, value, unit = "m", lang, error, idPrefix = "geo", onValue, onUnit }: Props) {
  const span = isSpan(fieldKey);
  const id = `${idPrefix}-${fieldKey}`;
  const metres = span ? typedToMetres(value, unit) : null;
  return (
    <div className="geo-field" data-testid={`geo-field-${fieldKey}`} data-invalid={error ? "true" : undefined}>
      <label htmlFor={id}>
        <span>
          {span ? shortLabel(fieldKey, lang) : inputLabel(fieldKey, lang)} <b aria-hidden="true" className="geo-req">*</b>
        </span>
      </label>
      <div className="geo-row">
        <input
          id={id}
          dir="ltr"
          inputMode="decimal"
          required
          aria-required="true"
          aria-invalid={error ? "true" : undefined}
          aria-describedby={error ? `${id}-err` : span && unit !== "m" ? `${id}-conv` : undefined}
          placeholder={PLACEHOLDER[fieldKey]}
          value={value}
          onChange={(e) => onValue(e.target.value)}
        />
        {span && onUnit ? (
          <select
            aria-label={lang === "fa" ? `واحد ${shortLabel(fieldKey, lang)}` : `${shortLabel(fieldKey, lang)} unit`}
            value={unit}
            onChange={(e) => onUnit(e.target.value as LengthUnit)}
          >
            {LENGTH_UNITS.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      {span && unit !== "m" && metres !== null ? (
        <small id={`${id}-conv`} className="muted geo-conv" data-testid={`geo-conv-${fieldKey}`}>
          = {metres} m
        </small>
      ) : null}
      {error ? (
        <small id={`${id}-err`} role="alert" className="geo-error">
          {error}
        </small>
      ) : null}
    </div>
  );
}
