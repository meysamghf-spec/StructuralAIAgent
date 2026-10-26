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
  summary: Record<string, unknown>;
  job_id?: string;
  filename?: string;
};

const cache = new Map<string, Promise<ChatRun[]>>();

export function listProjectChatRuns(projectId: string, fresh = false): Promise<ChatRun[]> {
  if (fresh || !cache.has(projectId)) {
    const p = apiFetch<{ runs: ChatRun[] }>(`/api/v1/conversations/project-runs/${encodeURIComponent(projectId)}`)
      .then((r) => r.runs ?? [])
      .catch((e) => {
        cache.delete(projectId);
        throw e;
      });
    cache.set(projectId, p);
  }
  return cache.get(projectId)!;
}

/** If this browser has no saved frame for the project, restore the latest frame analysis run in chat (any device). */
export async function hydrateFrame3dFromServer(projectId: string | null): Promise<boolean> {
  if (!projectId || loadFrame3dInputs(projectId)) return false;
  try {
    const runs = await listProjectChatRuns(projectId);
    const usable = (r: ChatRun) =>
      r.kind === "frame3d_analysis" &&
      !!r.inputs &&
      !/missing|fail|error|blocked/i.test(r.status) &&
      r.inputs.bays_x != null &&
      r.inputs.bays_y != null &&
      r.inputs.storeys != null;
    const last = runs.find(usable);
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
