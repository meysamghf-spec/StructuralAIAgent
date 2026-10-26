import { getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";

export type AutocadChatResult = {
  jobId: string;
  kind: "prompt" | "vectorize";
  title: string;
  filename: string;
  layers: string[];
  review: { status: string; note: string };
  projectFileId: string | null;
};

export type AutocadJobMeta = {
  id: string;
  kind: "prompt" | "vectorize";
  source: string;
  project_id: string | null;
  project_file_id: string | null;
  layers: string[];
  review: { status: string; note: string };
  created_at: string;
  summary: Record<string, unknown>;
};

export function mapAutocadResult(raw: unknown): AutocadChatResult | null {
  if (!raw || typeof raw !== "object") return null;
  const d = raw as Record<string, unknown>;
  if (typeof d.job_id !== "string") return null;
  return {
    jobId: d.job_id,
    kind: d.kind === "vectorize" ? "vectorize" : "prompt",
    title: String(d.title ?? "AutoCAD drawing"),
    filename: String(d.filename ?? `${d.job_id}.dxf`),
    layers: Array.isArray(d.layers) ? d.layers.map(String) : [],
    review: (d.review as AutocadChatResult["review"]) ?? { status: "not_required", note: "" },
    projectFileId: typeof d.project_file_id === "string" ? d.project_file_id : null,
  };
}

const base = () => `${getApiBaseUrl()}/api/v1/autocad`;

async function ok(res: Response): Promise<Response> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? body?.detail ?? `Request failed (${res.status})`);
  }
  return res;
}

export async function fetchAutocadPreview(jobId: string): Promise<string> {
  return (await ok(await fetch(`${base()}/jobs/${jobId}/preview.svg`, { headers: getAuthHeaders() }))).text();
}

export async function downloadAutocadDxf(jobId: string, filename: string): Promise<void> {
  const blob = await (await ok(await fetch(`${base()}/jobs/${jobId}/drawing.dxf`, { headers: getAuthHeaders() }))).blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function reviewAutocadJob(jobId: string, decision: "accept" | "flag", note = "") {
  const res = await fetch(`${base()}/jobs/${jobId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ decision, note }),
  });
  return (await (await ok(res)).json()) as { review: { status: string; note: string } };
}

export async function listAutocadJobs(projectId?: string | null): Promise<AutocadJobMeta[]> {
  const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await ok(await fetch(`${base()}/jobs${q}`, { headers: getAuthHeaders() }));
  return ((await res.json()) as { jobs: AutocadJobMeta[] }).jobs;
}

// ---------------------------------------------------------------- architectural sets
export type ArchSheet = { no: string; title_en: string; title_fa: string; kind: string; scale: number; dxf: string; png?: string; pdf?: string };
export type ArchSetMeta = {
  id: string;
  title: string;
  created_at?: string;
  project_id?: string | null;
  sheets: ArchSheet[];
  pdf?: string | null;
  zip?: string | null;
  checks?: string[][];
  assumptions?: string[];
  warnings?: string[];
};

export async function listArchSets(projectId?: string | null): Promise<ArchSetMeta[]> {
  const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await ok(await fetch(`${base()}/arch-sets${q}`, { headers: getAuthHeaders() }));
  const raw = ((await res.json()) as { sets?: unknown } | null)?.sets;
  return (Array.isArray(raw) ? (raw as ArchSetMeta[]) : []).map((s) => ({ ...s, sheets: Array.isArray(s?.sheets) ? s.sheets : [] }));
}

export async function fetchArchFile(setId: string, name: string): Promise<Blob> {
  return (await ok(await fetch(`${base()}/arch-sets/${setId}/files/${encodeURIComponent(name)}`, { headers: getAuthHeaders() }))).blob();
}

export async function downloadArchFile(setId: string, name: string): Promise<void> {
  const url = URL.createObjectURL(await fetchArchFile(setId, name));
  const a = document.createElement("a");
  a.href = url;
  a.download = `arch-${setId.slice(0, 6)}-${name}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
