import { getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";
import { latestImport } from "./model-import";

export type RectCm = [number, number];
export type SectionLists = {
  beams: (number[] | string)[];
  columns: (number[] | string)[];
  braces: (number[] | string)[];
  rebar_mm: number[];
  materials: { fc_mpa?: number; fy_mpa?: number; steel_fy_mpa?: number };
  member_types: { name: string; type: string; positions?: string[]; storeys?: (number | string)[]; direction?: string; candidates: (number[] | string)[] }[];
  found?: boolean;
};

export type OptGroup = {
  group: string; label: string; type: string; section: string; members: number; DC: number;
  design?: string; bars?: string; top_bars?: string; bottom_bars?: string; stirrups?: string; ties?: string;
  rebar_kg?: number; steel_kg?: number; notes?: string[]; deflection_ok?: boolean;
};

export type OptQuantities = { concrete_m3: number; rebar_kg: number; formwork_m2: number; steel_kg: number };
export type CostBreakdown = {
  components: { concrete: number; rebar: number; formwork: number; steel: number };
  total: number; share_pct: { concrete: number; rebar: number; formwork: number; steel: number }; steel_weight_kg: number;
};

export type OptResult = {
  status: string; feasible: boolean; cost: number; initial_cost: number | null; initial_feasible?: boolean | null; currency: string;
  evaluations: number; elapsed_s: number; drift_ratio: number;
  quantities: { concrete_m3: number; rebar_kg: number; formwork_m2: number; steel_kg: number };
  initial_quantities?: OptQuantities | null;
  cost_breakdown?: { initial: CostBreakdown | null; final: CostBreakdown | null };
  groups: OptGroup[]; assumptions: string[]; assumed_inputs?: string[];
  settings: Record<string, unknown> & { rebar_mm?: number[]; groups?: number };
  history: { eval: number; cost: number; feasible: boolean; best: number }[];
};

export type OptJob = {
  id: string; status: "queued" | "running" | "done" | "cancelled" | "error";
  progress: { fraction?: number; phase?: string; evals?: number; best_cost?: number; best_feasible?: boolean; elapsed_s?: number };
  result: OptResult | null; error: string | null;
};

export type JobRequest = {
  source: "frame" | "model";
  project_id?: string | null;
  inputs?: Record<string, unknown> | null;
  model?: Record<string, unknown> | null;
  section_text?: string;
  lists?: SectionLists | null;
  options?: { time_budget_s?: number; max_evals?: number; storey_band?: number; ductility?: string; prices?: Record<string, number> };
};

export class OptApiError extends Error {
  constructor(public status: number, message: string, public fa: string) { super(message); }
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/optimization-full${path}`, {
    ...init, headers: { ...getAuthHeaders(), ...(init.headers || {}) }, cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const d = body?.detail ?? body?.error?.details ?? body?.error?.message;
    if (d && typeof d === "object" && "en" in d) throw new OptApiError(res.status, String(d.en), String(d.fa ?? d.en));
    const msg = typeof d === "string" ? d : body?.error?.message ?? `Request failed (${res.status})`;
    throw new OptApiError(res.status, msg, msg);
  }
  return res.json() as Promise<T>;
}

const json = { "Content-Type": "application/json" };

export async function parseSections(text: string, file?: File | null): Promise<SectionLists> {
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("text", text);
    return (await call<{ lists: SectionLists }>("/parse-sections-file", { method: "POST", body: fd })).lists;
  }
  return (await call<{ lists: SectionLists }>("/parse-sections", { method: "POST", headers: json, body: JSON.stringify({ text }) })).lists;
}

export async function startJob(req: JobRequest): Promise<OptJob> {
  let body = req;
  if (req.source === "model" && !req.model && req.project_id) {
    const st = await latestImport(req.project_id);
    if (!st) throw new OptApiError(409, "No imported model in this project yet.", "هنوز مدلی در این پروژه وارد نشده است.");
    body = { ...req, model: st.model as unknown as Record<string, unknown> };
  }
  return (await call<{ job: OptJob }>("/jobs", { method: "POST", headers: json, body: JSON.stringify(body) })).job;
}

export async function getJob(id: string): Promise<OptJob> {
  return (await call<{ job: OptJob }>(`/jobs/${encodeURIComponent(id)}`, { method: "GET" })).job;
}

export async function cancelJob(id: string): Promise<void> {
  await call(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
}

/** Human label of a candidate: [b, h] metres → "40×60 cm", steel names unchanged. */
export function candLabel(c: number[] | string): string {
  return typeof c === "string" ? c : `${Math.round(c[0] * 100)}×${Math.round(c[1] * 100)}`;
}

/** Bars text of a group (columns: bars, beams: top / bottom). */
export function barsLabel(g: OptGroup): string {
  if (g.bars) return g.bars;
  if (g.top_bars || g.bottom_bars) return `بالا ${g.top_bars ?? "—"} / پایین ${g.bottom_bars ?? "—"}`;
  return "—";
}

/** Top/bottom rebar as separate lines (Persian labels) for stacked display; null when only a single bars string exists. */
export function barsLines(g: OptGroup): { label: string; value: string }[] | null {
  if (g.bars || !(g.top_bars || g.bottom_bars)) return null;
  return [
    { label: "بالا", value: g.top_bars ?? "—" },
    { label: "پایین", value: g.bottom_bars ?? "—" },
  ];
}

export function savingsPct(r: Pick<OptResult, "cost" | "initial_cost">): number | null {
  if (!r.initial_cost || !(r.initial_cost > 0)) return null;
  return Math.round(((r.initial_cost - r.cost) / r.initial_cost) * 1000) / 10;
}

/** Persian wording of the cost change vs. the starting design (never a negative "کاهش"). */
export function costChangeText(r: Pick<OptResult, "cost" | "initial_cost"> & { initial_feasible?: boolean | null }): string {
  const p = savingsPct(r);
  if (p == null) return "";
  if (p > 0) return `${fmtNum(p, 1)}٪ کاهش هزینه نسبت به طرح اولیه`;
  if (p < 0) {
    const why = r.initial_feasible === false ? " (طرح اولیه کنترل‌ها را پاس نمی‌کرد)" : "";
    return `افزایش هزینه ${fmtNum(-p, 1)}٪ برای رسیدن به طرح قابل‌قبول${why}`;
  }
  return "بدون تغییر هزینه نسبت به طرح اولیه";
}

export function isActive(job: OptJob | null): boolean {
  return !!job && (job.status === "queued" || job.status === "running");
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toLocaleString("fa-IR", { maximumFractionDigits: digits });
}

export type ProjectFrame = {
  source: "frame" | "optimization" | "chat_text" | "default";
  label: { en: string; fa: string };
  chat_title: string | null;
  inputs: Record<string, unknown>;
  from_chat: string[];
  assumed: string[];
};

/** The project's frame from its whole chat history (same resolver as optimization); defaults filled for missing geometry. */
// Several panels ask for the same project's frame at once (and again on every project switch): share one request
// per project for a short while so the server resolves the chat history once, not N times.
const frameCache = new Map<string, { at: number; p: Promise<ProjectFrame> }>();
const FRAME_TTL_MS = 30_000;

export async function getProjectFrame(projectId: string): Promise<ProjectFrame> {
  const hit = frameCache.get(projectId);
  if (hit && Date.now() - hit.at < FRAME_TTL_MS) return hit.p;
  const p = call<ProjectFrame>(`/project-frame?project_id=${encodeURIComponent(projectId)}`, { method: "GET" });
  frameCache.set(projectId, { at: Date.now(), p });
  p.catch(() => frameCache.delete(projectId));
  return p;
}
