import { apiFetch, type ProjectListResponse } from "@/lib/api";
import { getCurrentProjectId, setCurrentProjectId } from "@/lib/current-project";

let pending: Promise<string | null> | null = null;

/** Workspace pages need a project: when none is selected yet, pick the most recently updated one. */
export function ensureCurrentProject(): Promise<string | null> {
  const pid = getCurrentProjectId();
  if (pid) return Promise.resolve(pid);
  if (!pending) {
    pending = apiFetch<ProjectListResponse>("/api/v1/projects")
      .then((r) => {
        const list = [...(r.projects ?? [])] as Array<{ id: string; updated_at?: string; created_at?: string }>;
        list.sort((a, b) => String(b.updated_at ?? b.created_at ?? "").localeCompare(String(a.updated_at ?? a.created_at ?? "")));
        const id = list[0]?.id ?? null;
        if (id && !getCurrentProjectId()) setCurrentProjectId(id);
        return id;
      })
      .catch(() => null)
      .finally(() => {
        pending = null;
      });
  }
  return pending;
}
