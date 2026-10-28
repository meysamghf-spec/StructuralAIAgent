import { apiFetch } from "./api";
import { FRAME3D_EVENT, loadFrame3dInputs, saveFrame3dInputs } from "./frame3d-store";

export type ChatRun = {
  message_id: string;
  conversation_id: string;
  conversation_title: string;
  created_at: string;
  kind: string;
  label: string;
  status: string;
  inputs: Record<string, unknown> | null;
  optimization?: unknown;
  summary: Record<string, unknown>;
  job_id?: string;
  filename?: string;
};

const cache = new Map<string, Promise<ChatRun[]>>();

export function listProjectChatRuns(projectId: string, fresh = false): Promise<ChatRun[]> {
  if (fresh || !cache.has(projectId)) {
    const p = apiFetch<{ runs: ChatRun[] }>(`/api/v1/conversations/project-runs/${encodeURIComponent(projectId)}`)
      .then((r) => (Array.isArray(r?.runs) ? r.runs.filter((x) => x && typeof x === "object") : []))
      .catch((e) => {
        cache.delete(projectId);
        throw e;
      });
    cache.set(projectId, p);
  }
  return cache.get(projectId)!;
}

const GEOMETRY_KEYS = ["storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m"] as const;

/** A frame run that can be re-run as is: not failed/missing and with every geometry input present. */
export function isUsableFrameRun(r: ChatRun): boolean {
  return (
    r.kind === "frame3d_analysis" &&
    !!r.inputs &&
    !/missing|fail|error|blocked|incomplete/i.test(r.status) &&
    GEOMETRY_KEYS.every((k) => r.inputs![k] != null)
  );
}

/**
 * The newest frame run that stopped for missing inputs, but ONLY when the project has no usable frame run
 * (otherwise the usable result is what is shown and the incomplete attempt is just history).
 */
export function incompleteFrameRun(runs: ChatRun[]): ChatRun | null {
  const frames = runs.filter((r) => r.kind === "frame3d_analysis");
  if (frames.some(isUsableFrameRun)) return null;
  return frames[0] ?? null;
}

/** If this browser has no saved frame for the project, restore the latest frame analysis run in chat (any device). */
export async function hydrateFrame3dFromServer(projectId: string | null): Promise<boolean> {
  if (!projectId || loadFrame3dInputs(projectId)) return false;
  try {
    const runs = await listProjectChatRuns(projectId);
    const last = runs.find(isUsableFrameRun);
    if (!last?.inputs) return false;
    // Drop nulls so form defaults stay in place for anything the chat did not specify.
    const clean = Object.fromEntries(Object.entries(last.inputs).filter(([, v]) => v !== null && v !== undefined));
    saveFrame3dInputs(projectId, clean);
    if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(FRAME3D_EVENT));
    return true;
  } catch {
    return false;
  }
}
