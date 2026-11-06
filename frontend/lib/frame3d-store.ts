// Last 3D-frame inputs/payload per project, shared by chat cards and the Model/Analysis/Results/Design pages.
import { parseNumber, typedToMetres, type LengthUnit } from "./length-units";
const PREFIX = "sa.frame3d";

function key(kind: "inputs" | "payload", projectId: string | null): string {
  return `${PREFIX}.${kind}.${projectId || "none"}`;
}

function read<T>(k: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(k);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(k: string, value: unknown): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(k, JSON.stringify(value));
  } catch {
    /* quota exceeded: keep going without persistence */
  }
}

export const FRAME3D_EVENT = "sa:frame3d-updated";

export function saveFrame3dInputs(projectId: string | null, inputs: Record<string, unknown>): void {
  const clean = Object.fromEntries(Object.entries(inputs).filter(([k]) => !k.startsWith("_")));
  write(key("inputs", projectId), clean);
}

export function loadFrame3dInputs(projectId: string | null): Record<string, unknown> | null {
  return read<Record<string, unknown>>(key("inputs", projectId));
}

export function saveFrame3dPayload(projectId: string | null, payload: unknown): void {
  write(key("payload", projectId), payload);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(FRAME3D_EVENT));
}

/** Remove a stale result when a newer project-chat specification changes the model inputs. */
export function clearFrame3dPayload(projectId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key("payload", projectId));
  } catch {
    /* storage may be unavailable */
  }
}

export function loadFrame3dPayload(projectId: string | null): unknown {
  return read<unknown>(key("payload", projectId));
}

export type FrameFormField = { key: string; label: string; unit?: string; kind: "int" | "num" | "select"; options?: string[]; group: string };

export const FRAME_FORM_FIELDS: FrameFormField[] = [
  { key: "storeys", label: "Stories", kind: "int", group: "Geometry" },
  { key: "bays_x", label: "Bays in X", kind: "int", group: "Geometry" },
  { key: "bays_y", label: "Bays in Y", kind: "int", group: "Geometry" },
  { key: "bay_x_m", label: "Span X", unit: "m", kind: "num", group: "Geometry" },
  { key: "bay_y_m", label: "Span Y", unit: "m", kind: "num", group: "Geometry" },
  { key: "storey_height_m", label: "Story height", unit: "m", kind: "num", group: "Geometry" },
  { key: "column_b_m", label: "Column b", unit: "m", kind: "num", group: "Sections" },
  { key: "column_h_m", label: "Column h", unit: "m", kind: "num", group: "Sections" },
  { key: "beam_b_m", label: "Beam b", unit: "m", kind: "num", group: "Sections" },
  { key: "beam_h_m", label: "Beam h", unit: "m", kind: "num", group: "Sections" },
  { key: "slab_t_m", label: "Slab thickness", unit: "m", kind: "num", group: "Sections" },
  { key: "fc_mpa", label: "f'c", unit: "MPa", kind: "num", group: "Materials" },
  { key: "fy_mpa", label: "fy", unit: "MPa", kind: "num", group: "Materials" },
  { key: "dead_kn_m2", label: "Dead load", unit: "kN/m²", kind: "num", group: "Loads" },
  { key: "live_kn_m2", label: "Live load", unit: "kN/m²", kind: "num", group: "Loads" },
  { key: "roof_live_kn_m2", label: "Roof live load", unit: "kN/m²", kind: "num", group: "Loads" },
  { key: "wall_kn_m", label: "Perimeter wall", unit: "kN/m", kind: "num", group: "Loads" },
  { key: "seismic_code", label: "Seismic code", kind: "select", options: ["IRAN_2800", "ASSUMED_C"], group: "Seismic (2800)" },
  { key: "zone", label: "Seismic hazard", kind: "select", options: ["VERY_HIGH", "HIGH", "MODERATE", "LOW"], group: "Seismic (2800)" },
  { key: "soil", label: "Soil type", kind: "select", options: ["I", "II", "III", "IV"], group: "Seismic (2800)" },
  { key: "importance", label: "Importance I", kind: "num", group: "Seismic (2800)" },
  { key: "system", label: "Lateral system", kind: "select", options: ["RC_IMF", "RC_SMF", "RC_OMF"], group: "Seismic (2800)" },
  { key: "seismic_c", label: "C (if assumed)", kind: "num", group: "Seismic (2800)" },
  { key: "design_code", label: "Design", kind: "select", options: ["MABHAS9", "NONE"], group: "Design & foundation" },
  { key: "allowable_bearing_kpa", label: "Allowable bearing", unit: "kPa", kind: "num", group: "Design & foundation" },
];

export const DEFAULT_FRAME_INPUTS: Record<string, unknown> = {
  // storeys / bays_x / bays_y / bay_x_m / bay_y_m are REQUIRED and deliberately have NO default (placeholders only).
  storey_height_m: 3.2,
  column_b_m: 0.4, column_h_m: 0.4, beam_b_m: 0.3, beam_h_m: 0.45, slab_t_m: 0.12,
  fc_mpa: 30, fy_mpa: 400, dead_kn_m2: 6, live_kn_m2: 2, roof_live_kn_m2: 1.5, wall_kn_m: 7,
  seismic_code: "IRAN_2800", zone: "HIGH", soil: "II", importance: 1, system: "RC_IMF", seismic_c: null,
  design_code: "MABHAS9", allowable_bearing_kpa: 150, foundation: true,
};

/** Convert the form's string values to typed solver inputs (blank numeric -> null). */
export function formToInputs(
  values: Record<string, string>,
  lang: "en" | "fa",
  units: Partial<Record<string, LengthUnit>> = {},
): Record<string, unknown> {
  const out: Record<string, unknown> = { foundation: true, lang };
  for (const f of FRAME_FORM_FIELDS) {
    const raw = (values[f.key] ?? "").trim();
    if (f.kind === "select") out[f.key] = raw || null;
    else if (raw === "") out[f.key] = null;
    else if (units[f.key] && units[f.key] !== "m") out[f.key] = typedToMetres(raw, units[f.key]!);
    else {
      const n = parseNumber(raw);
      out[f.key] = n !== null ? (f.kind === "int" ? Math.round(n) : n) : null;
    }
  }
  if (out.seismic_code === "IRAN_2800") out.seismic_c = null;
  return Object.fromEntries(Object.entries(out).filter(([, v]) => v !== null));
}

/** Placeholders (not values!) for the required geometry fields. */
export const GEOMETRY_PLACEHOLDERS: Record<string, string> = {
  storeys: "e.g. 3", bays_x: "e.g. 2", bays_y: "e.g. 2", bay_x_m: "e.g. 5", bay_y_m: "e.g. 5",
};

export function inputsToForm(inputs: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of FRAME_FORM_FIELDS) {
    const v = inputs[f.key];
    out[f.key] = v === null || v === undefined ? "" : String(v);
  }
  return out;
}
