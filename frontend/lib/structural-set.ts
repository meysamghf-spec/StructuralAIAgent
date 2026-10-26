import { getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";

export type StructuralSheet = {
  sheet_no: string;
  title: string;
  title_fa: string;
  scale: string;
  job_id: string;
  filename: string;
  file_id: string | null;
};

export type StructuralSet = {
  id: string;
  project_id: string | null;
  created_at?: string;
  sheets: StructuralSheet[];
  notes: string[];
  pdf: boolean;
  pdf_file_id?: string | null;
  frame?: { storeys: number; bays_x: number; bays_y: number; bay_x_m: number; bay_y_m: number; storey_height_m: number };
};

const base = () => `${getApiBaseUrl()}/api/v1/autocad`;

async function ok(res: Response): Promise<Response> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? body?.detail ?? `Request failed (${res.status})`);
  }
  return res;
}

export function mapStructuralSet(raw: unknown): StructuralSet | null {
  if (!raw || typeof raw !== "object") return null;
  const d = raw as Record<string, unknown>;
  if (typeof d.id !== "string" || !Array.isArray(d.sheets)) return null;
  return {
    id: d.id,
    project_id: typeof d.project_id === "string" ? d.project_id : null,
    sheets: d.sheets as StructuralSheet[],
    notes: Array.isArray(d.notes) ? d.notes.map(String) : [],
    pdf: !!d.pdf,
    pdf_file_id: typeof d.pdf_file_id === "string" ? d.pdf_file_id : null,
  };
}

export async function listStructuralSets(projectId?: string | null): Promise<StructuralSet[]> {
  const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await ok(await fetch(`${base()}/structural-sets${q}`, { headers: getAuthHeaders() }));
  const raw = ((await res.json()) as { sets?: unknown } | null)?.sets;
  return Array.isArray(raw) ? (raw.map(mapStructuralSet).filter(Boolean) as StructuralSet[]) : [];
}

export async function generateStructuralSet(projectId: string | null): Promise<StructuralSet> {
  const res = await fetch(`${base()}/structural-set`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ project_id: projectId }),
  });
  return (await (await ok(res)).json()) as StructuralSet;
}

export async function downloadStructuralSetPdf(setId: string): Promise<void> {
  const blob = await (await ok(await fetch(`${base()}/structural-sets/${setId}/set.pdf`, { headers: getAuthHeaders() }))).blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "structural-drawing-set.pdf";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
