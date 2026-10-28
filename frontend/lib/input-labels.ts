// Friendly fa/en labels for frame inputs (instead of raw keys like bays_x) + required-geometry check.
export type InputLang = "en" | "fa";

export const INPUT_LABELS: Record<string, { en: string; fa: string; unit?: "m" }> = {
  storeys: { en: "Number of storeys", fa: "تعداد طبقات" },
  bays_x: { en: "Number of bays in X", fa: "تعداد دهانه x" },
  bays_y: { en: "Number of bays in Y", fa: "تعداد دهانه y" },
  bay_x_m: { en: "Span in X (m)", fa: "طول دهانه x (متر)", unit: "m" },
  bay_y_m: { en: "Span in Y (m)", fa: "طول دهانه y (متر)", unit: "m" },
  storey_height_m: { en: "Storey height (m)", fa: "ارتفاع طبقه (متر)", unit: "m" },
};

/** Required geometry — never silently guessed (unless the user explicitly asks to assume defaults). */
export const REQUIRED_GEOMETRY = ["storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m"] as const;
export const SPAN_KEYS = ["bay_x_m", "bay_y_m"] as const;
export const COUNT_KEYS = ["storeys", "bays_x", "bays_y"] as const;

export function inputLabel(key: string, lang: InputLang): string {
  const l = INPUT_LABELS[key];
  return l ? l[lang] : key.replace(/_/g, " ");
}

export function inputLabels(keys: string[], lang: InputLang): string {
  return keys.map((k) => inputLabel(k, lang)).join(lang === "fa" ? "، " : ", ");
}

function blank(v: unknown): boolean {
  return v === null || v === undefined || v === "" || (typeof v === "number" && !Number.isFinite(v));
}

/** Required geometry keys that are absent OR empty. `null` inputs (nothing run yet) → []. */
export function missingGeometry(inputs: Record<string, unknown> | null | undefined): string[] {
  if (!inputs || typeof inputs !== "object") return [];
  return REQUIRED_GEOMETRY.filter((k) => blank(inputs[k]));
}

/** True when storeys, bays_x, bays_y and both spans are all present. */
export function geometryComplete(inputs: Record<string, unknown> | null | undefined): boolean {
  return !!inputs && typeof inputs === "object" && missingGeometry(inputs).length === 0;
}
