// Client for /api/v1/model-import (ETABS .e2k, SAP2000 .s2k, SAFE .f2k, AutoCAD .dxf -> engineer review -> SAIA engine).
// Every number shown comes from the backend engine; nothing here computes structural results.
import { getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";

export type ImportIssue = { id: string; severity: "blocking" | "approximated" | "ignored"; code: string; item: string; en: string; fa: string; count: number; confirmed?: boolean };
export type ImportReview = { counts: Record<string, number>; issues: ImportIssue[]; assumptions: { en: string; fa: string }[]; blocking: number; can_analyze: boolean; requires_confirmation: string[] };
export type MemberForces = { N: number; V: number; M: number; T: number };
export type SeismicInfo = {
  zone: string; soil: string; system: string; system_label: string; A: number; R: number; Cd: number; I: number; T_empirical_s: number;
  B: number; C: number; k: number; drift_limit: number; H_m: number; storeys: number; W_kN: number; V_kN: number;
  levels: { z: number; W_kN: number; F_kN: number }[]; from_file?: boolean; generated?: { pattern: string; dir: string }[];
};
export type ModalMode = { mode: number; T: number; f: number; mass_ratio_x: number; mass_ratio_y: number; cum_x: number; cum_y: number };
export type DesignRow = { member: string; type: string; section: string; kind: "steel" | "concrete"; ratio: number; ok: boolean; detail: string; case?: string; As_top_cm2?: number | null; As_bottom_cm2?: number | null };
export type ImportAnalysis = {
  engine: string; units: Record<string, string>;
  counts?: Record<string, number>;
  cases: Record<string, { factors: Record<string, number>; base_reaction_kN: number[]; max_displacement_m: number; max_displacement_node: string }>;
  governing_members: (MemberForces & { member: string })[]; notes: string[];
  assumptions?: { en: string; fa: string }[];
  seismic?: SeismicInfo | null;
  pdelta?: { applied?: boolean; amplification?: Record<string, number>; iterations?: number; case?: string } & Record<string, unknown>;
  modal?: { modes: ModalMode[]; total_mass_t?: number } | null;
  response_spectrum?: { base_shear_kN: Record<string, number>; scale: Record<string, number>; static_base_shear_kN: number } | null;
  drifts?: { case: string; max: number; limit?: number; level?: number; ok?: boolean }[];
  equilibrium?: Record<string, number>;
  slabs?: { count: number; one_way: number; to_nodes: number };
  design?: { method: string; count: number; failing: number; members: DesignRow[]; materials?: Record<string, number> } | null;
};
export type ImportState = { stage: string; model: Record<string, unknown> & { filename?: string; sections?: Record<string, unknown>; load_patterns?: Record<string, unknown> }; review: ImportReview; analysis: ImportAnalysis | null; state_file_id?: string };
export type ReviewEdits = {
  sections?: Record<string, Record<string, number | string>>;
  beam_line_loads?: { pattern: string; w: number; story?: string }[];
  area_loads?: { pattern: string; q: number; story?: string }[];
  seismic?: { zone?: string; soil?: string; importance?: number; system?: string };
  wind?: { V_kmh?: number; enabled?: boolean };
  pdelta?: boolean; rigid_diaphragms?: boolean;
  dxf?: { storeys: number; height: number; column_section?: string };
  confirmed?: string[];
};

export const ZONES = ["VERY_HIGH", "HIGH", "MODERATE", "LOW"] as const;
export const SOILS = ["I", "II", "III", "IV"] as const;
export const SYSTEMS = ["RC_SMF", "RC_IMF", "RC_OMF", "STEEL_SMF", "STEEL_IMF", "STEEL_OMF"] as const;

export const ACCEPTED_EXTENSIONS = [".e2k", ".s2k", ".f2k", ".dxf"];
/** Kept for compatibility: every planned format is now supported. */
export const NEXT_PHASE_EXTENSIONS: string[] = [];

export class ImportApiError extends Error {
  constructor(public status: number, public en: string, public fa: string) { super(en); }
}

/** Client-side pre-check; the backend re-validates. Returns null when the file may be sent. */
export function precheckFile(name: string): { en: string; fa: string } | null {
  const ext = name.toLowerCase().slice(name.lastIndexOf("."));
  if (ext === ".dwg") return { en: "DWG is not supported. In AutoCAD use Save As → DXF (ASCII) and upload the .dxf.", fa: "فایل DWG پشتیبانی نمی‌شود. در اتوکد با Save As آن را DXF (ASCII) ذخیره و فایل ‎.dxf را بارگذاری کنید." };
  if (!ACCEPTED_EXTENSIONS.includes(ext)) return { en: "Unsupported file. Upload ETABS .e2k, SAP2000 .s2k, SAFE .f2k or AutoCAD .dxf.", fa: "فایل پشتیبانی نمی‌شود. ETABS ‎.e2k، SAP2000 ‎.s2k، SAFE ‎.f2k یا AutoCAD ‎.dxf بارگذاری کنید." };
  return null;
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/model-import${path}`, { ...init, headers: { ...getAuthHeaders(), ...(init.headers || {}) }, cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const d = body?.detail ?? body?.error?.details ?? body?.error?.message;
    if (d && typeof d === "object" && "en" in d) throw new ImportApiError(res.status, String(d.en), String(d.fa ?? d.en));
    const msg = typeof d === "string" ? d : body?.error?.message ?? `Request failed (${res.status})`;
    throw new ImportApiError(res.status, msg, msg);
  }
  return res.json() as Promise<T>;
}

export function parseImport(file: File, projectId: string | null): Promise<ImportState> {
  const fd = new FormData();
  fd.append("file", file);
  if (projectId) fd.append("project_id", projectId);
  return call("/parse", { method: "POST", body: fd });
}

export function reviewImport(model: ImportState["model"], edits: ReviewEdits, projectId: string | null): Promise<ImportState> {
  return call("/review", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, edits, project_id: projectId }) });
}

export function analyzeImport(model: ImportState["model"], projectId: string | null): Promise<ImportState> {
  return call("/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, project_id: projectId }) });
}

export async function latestImport(projectId: string): Promise<ImportState | null> {
  const r = await call<{ state: ImportState | null }>(`/latest?project_id=${encodeURIComponent(projectId)}`, { method: "GET" });
  return r.state;
}

/** Section edits for blocking section issues: rectangle b,h in mm -> metres, or explicit properties. */
export function sectionEditFromMm(b_mm: number, h_mm: number): Record<string, number> | null {
  if (!(b_mm > 0 && h_mm > 0)) return null;
  return { b: b_mm / 1000, h: h_mm / 1000 };
}

/** Catalog profile names accepted by the backend (IPE, HEA, HEB, UNP, BOX, PIPE). */
export function isCatalogName(name: string): boolean {
  return /^(IPE|HE[AB]|UNP|BOX|PIPE)\s*\d|^HE\d+[AB]$/i.test(name.trim());
}

export function fmt(v: number, digits = 3): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) < 1e-9) return "0";
  return Number(v.toPrecision(digits + 1)).toLocaleString("en-US", { maximumFractionDigits: 6 });
}
