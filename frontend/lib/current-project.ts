// Current project shared by every page (sidebar, chat dock, workspace pages) via localStorage.
const KEY = "sa.currentProjectId";
export const PROJECT_EVENT = "sa:current-project";

export function getCurrentProjectId(): string | null {
  if (typeof window === "undefined") return null;
  const fromUrl = new URLSearchParams(window.location.search).get("project");
  if (fromUrl) return fromUrl;
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setCurrentProjectId(id: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (id) window.localStorage.setItem(KEY, id);
    else window.localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
  // getCurrentProjectId() prefers ?project=, so a stale URL value would keep pages on the previous project.
  try {
    const url = new URL(window.location.href);
    if (url.searchParams.has("project") && url.searchParams.get("project") !== id) {
      if (id) url.searchParams.set("project", id);
      else url.searchParams.delete("project");
      window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
    }
  } catch {
    /* non-browser environment */
  }
  window.dispatchEvent(new CustomEvent(PROJECT_EVENT, { detail: id }));
}

/** Chat URL for a project (the chat page selects it from ?project=). */
export function projectChatHref(id: string): string {
  return `/?project=${encodeURIComponent(id)}`;
}
