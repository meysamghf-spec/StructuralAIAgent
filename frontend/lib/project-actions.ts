import { apiFetch, type CreateProjectResponse, type ProjectSummary } from "@/lib/api";
import { setCurrentProjectId } from "@/lib/current-project";

/** Dispatched after a project is created so every project list on the page refreshes. */
export const PROJECTS_EVENT = "sa:projects-changed";
export const PROJECT_NAME_MAX = 120;

/** Trim, collapse inner whitespace and cap the length. Empty string means "not a valid name". */
export function cleanProjectName(raw: string): string {
  return raw.replace(/\s+/g, " ").trim().slice(0, PROJECT_NAME_MAX).trim();
}

/** Create a project through the existing API, make it the active project everywhere, return it. */
export async function createProjectAndSwitch(rawName: string): Promise<ProjectSummary> {
  const name = cleanProjectName(rawName);
  if (!name) throw new Error("Project name is required.");
  const created = await apiFetch<CreateProjectResponse>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(PROJECTS_EVENT, { detail: created.project }));
  setCurrentProjectId(created.project.id);
  return created.project;
}
