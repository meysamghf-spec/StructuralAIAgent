// Pure helpers for the Design page ("Design" button): readiness, status chips, governing member and section sizes.
// Everything shown is derived from the engine output (Mabhas 9 member design + isolated footings of POST /api/v1/frame3d/run).
import type { Frame3dFoundation, Frame3dResults } from "./chat-types";
import { FRAME_FORM_FIELDS } from "./frame3d-store";

export type Row = Record<string, string | number | null>;
export type DesignChip = "pass" | "review" | "fail";

export const DESIGN_REQUIRED_KEYS = ["storeys", "bays_x", "bays_y"] as const;

export type MissingItem = { id: string; label: string; href: "/workspace/analysis" | "/workspace/model" };

/** Human label of a frame input key (never the raw key, e.g. "Bays in X" instead of bays_x). */
export function inputLabel(key: string): string {
  return FRAME_FORM_FIELDS.find((f) => f.key === key)?.label ?? key;
}

function isBlank(v: unknown): boolean {
  return v === null || v === undefined || v === "";
}

export type DesignReadiness = { ready: boolean; missing: MissingItem[] };

/**
 * The design runs on the saved model inputs and the latest analysis result of the project.
 * Missing pieces are listed with a human label and the page where they are fixed.
 */
export function designReadiness(
  inputs: Record<string, unknown> | null | undefined,
  payload: unknown,
): DesignReadiness {
  const missing: MissingItem[] = [];
  const p = payload as { status?: string; missing_inputs?: unknown[] } | null;
  const payloadMissing = p && typeof p === "object" && Array.isArray(p.missing_inputs)
    ? p.missing_inputs.filter((k): k is string => typeof k === "string" && k !== "frame_model")
    : [];
  if (!inputs || typeof inputs !== "object") {
    missing.push({ id: "model", label: "3D frame model", href: "/workspace/model" });
  } else {
    for (const k of DESIGN_REQUIRED_KEYS) {
      if (isBlank(inputs[k])) missing.push({ id: k, label: inputLabel(k), href: "/workspace/model" });
    }
  }
  for (const k of payloadMissing) {
    if (!missing.some((m) => m.id === k)) missing.push({ id: k, label: inputLabel(k), href: "/workspace/model" });
  }
  const analysed = !!p && typeof p === "object" && p.status === "completed";
  if (!analysed) missing.push({ id: "analysis", label: "Analysis results", href: "/workspace/analysis" });
  return { ready: missing.length === 0, missing };
}

/** Engine status code → chip. Unknown codes are "needs review" (never silently a pass). */
export function chipOf(status: string | null | undefined): DesignChip {
  const s = String(status ?? "").toUpperCase();
  if (s === "PASS") return "pass";
  if (s === "FAIL" || s === "OVERLAP" || s === "FAILED") return "fail";
  return "review";
}

export function dcChip(dc: number | null): DesignChip | null {
  if (dc === null) return null;
  return dc > 1 ? "fail" : "pass";
}

function num(v: unknown): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string") {
    const n = Number.parseFloat(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export type Governing = { group: string; dc: number; check: "flexure" | "shear" | "axial-flexure" };

/** Member group with the largest demand/capacity ratio over beam flexure, beam shear and column checks. */
export function governingMember(design: Pick<NonNullable<Frame3dResults["design"]>, "beams" | "columns">): Governing | null {
  let best: Governing | null = null;
  const consider = (group: unknown, dc: number | null, check: Governing["check"]) => {
    if (dc === null) return;
    if (!best || dc > best.dc) best = { group: String(group ?? "—"), dc, check };
  };
  for (const r of design.beams) {
    consider(r.group, num(r.DC_flexure), "flexure");
    consider(r.group, num(r.DC_shear), "shear");
  }
  for (const r of design.columns) consider(r.group, num(r.DC), "axial-flexure");
  return best;
}

/** Section "b×h (mm)" of a design group, from the inputs echoed by the engine (per-storey override first). */
export function sectionText(kind: "beam" | "column", row: Row, inputs: Record<string, unknown> | null | undefined): string {
  if (!inputs) return "—";
  const storey = num(row.storey);
  const gs = inputs.group_sections as Record<string, unknown> | null | undefined;
  const key = `${kind === "beam" ? "B" : "C"}${storey ?? ""}`;
  const own = gs && typeof gs === "object" ? gs[key] : null;
  let b: number | null = null;
  let h: number | null = null;
  if (Array.isArray(own) && own.length >= 2) {
    b = num(own[0]);
    h = num(own[1]);
  } else {
    b = num(inputs[kind === "beam" ? "beam_b_m" : "column_b_m"]);
    h = num(inputs[kind === "beam" ? "beam_h_m" : "column_h_m"]);
  }
  if (b === null || h === null) return "—";
  return `${Math.round(b * 1000)}×${Math.round(h * 1000)}`;
}

/** Largest D/C of a foundation row (bearing, one-way shear, punching, flexure). */
export function foundationMaxDc(f: Pick<Frame3dFoundation, "rows">): number | null {
  const all = f.rows.flatMap((r) => [num(r.bearing_dc), num(r.DC_oneway), num(r.DC_punching), num(r.DC_flexure)]).filter((v): v is number => v !== null);
  return all.length ? Math.max(...all) : null;
}

export function rowMaxDc(row: Row, keys: string[]): number | null {
  const v = keys.map((k) => num(row[k])).filter((x): x is number => x !== null);
  return v.length ? Math.max(...v) : null;
}

export const DESIGN_LAST_RUN_PREFIX = "sa.design.lastRun";
export type DesignLastRun = { at: string; ok: boolean };

export function loadDesignLastRun(projectId: string | null): DesignLastRun | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(`${DESIGN_LAST_RUN_PREFIX}.${projectId || "none"}`);
    const v = raw ? (JSON.parse(raw) as DesignLastRun) : null;
    return v && typeof v.at === "string" ? v : null;
  } catch {
    return null;
  }
}

export function saveDesignLastRun(projectId: string | null, value: DesignLastRun): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(`${DESIGN_LAST_RUN_PREFIX}.${projectId || "none"}`, JSON.stringify(value));
  } catch {
    /* storage unavailable */
  }
}

/**
 * Inputs for the Design button: the project's saved model with the Mabhas 9 member design switched on
 * (the only member-design code the engine supports) and the foundation design requested.
 */
export function designRunInputs(saved: Record<string, unknown>, lang: "en" | "fa"): { inputs: Record<string, unknown>; codeSwitchedOn: boolean } {
  const code = saved.design_code;
  const codeSwitchedOn = isBlank(code) || String(code).toUpperCase() === "NONE";
  return {
    inputs: { ...saved, ...(codeSwitchedOn ? { design_code: "MABHAS9" } : {}), foundation: true, lang },
    codeSwitchedOn,
  };
}
