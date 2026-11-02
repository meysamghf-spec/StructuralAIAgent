// Client for /api/v1/model-import (ETABS .e2k import -> engineer review -> SAIA frame3d analysis).
// Every number shown comes from the backend engine; nothing here computes structural results.
import { getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";

export type ImportIssue = { id: string; severity: "blocking" | "approximated" | "ignored"; code: string; item: string; en: string; fa: string; count: number; confirmed?: boolean };
export type ImportReview = { counts: Record<string, number>; issues: ImportIssue[]; assumptions: { en: string; fa: string }[]; blocking: number; can_analyze: boolean; requires_confirmation: string[] };
export type MemberForces = { N: number; V: number; M: number; T: number };
export type ImportAnalysis = {
  engine: string; units: Record<string, string>;
  cases: Record<string, { factors: Record<string, number>; base_reaction_kN: number[]; max_displacement_m: number; max_displacement_node: string }>;
  governing_members: (MemberForces & { member: string })[]; notes: string[];
};
export type ImportState = { stage: string; model: Record<string, unknown> & { filename?: string; sections?: Record<string, unknown>; load_patterns?: Record<string, unknown> }; review: ImportReview; analysis: ImportAnalysis | null; state_file_id?: string };
export type ReviewEdits = { sections?: Record<string, Record<string, number>>; beam_line_loads?: { pattern: string; w: number; story?: string }[]; confirmed?: string[] };

export const ACCEPTED_EXTENSIONS = [".e2k"];
export const NEXT_PHASE_EXTENSIONS = [".s2k", ".f2k", ".dxf"];

export class ImportApiError extends Error {
  constructor(public status: number, public en: string, public fa: string) { super(en); }
}

/** Client-side pre-check; the backend re-validates. Returns null when the file may be sent. */
export function precheckFile(name: string): { en: string; fa: string } | null {
  const ext = name.toLowerCase().slice(name.lastIndexOf("."));
  if (ext === ".dwg") return { en: "DWG is not supported. In AutoCAD use Save As → DXF and upload the .dxf (DXF import comes in the next phase).", fa: "فایل DWG پشتیبانی نمی‌شود. در اتوکد با Save As آن را DXF ذخیره کنید (ورود DXF در فاز بعد)." };
  if (NEXT_PHASE_EXTENSIONS.includes(ext)) return { en: `${ext} import is planned for the next phase. ETABS .e2k works now.`, fa: `ورود ${ext} در فاز بعد اضافه می‌شود. فعلاً ETABS ‎.e2k پشتیبانی می‌شود.` };
  if (!ACCEPTED_EXTENSIONS.includes(ext)) return { en: "Unsupported file. Upload an ETABS .e2k text file.", fa: "فایل پشتیبانی نمی‌شود. فایل متنی ETABS ‎.e2k بارگذاری کنید." };
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

export function fmt(v: number, digits = 3): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) < 1e-9) return "0";
  return Number(v.toPrecision(digits + 1)).toLocaleString("en-US", { maximumFractionDigits: 6 });
}
