// Sidebar navigation. Every page is complete and listed; nothing is hidden.
export type NavItem = { href: string; label: string };

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Chat" },
  { href: "/projects", label: "Projects" },
  { href: "/projects/new", label: "New Project" },
  { href: "/workspace/model", label: "Model" },
  { href: "/workspace/analysis", label: "Analysis" },
  { href: "/workspace/results", label: "Results" },
  { href: "/workspace/design", label: "Design" },
  { href: "/workspace/foundation", label: "Foundation" },
  { href: "/workspace/cad", label: "CAD" },
  { href: "/workspace/reports", label: "Reports" },
  { href: "/workspace/validation", label: "Validation" },
  { href: "/workspace/files", label: "Files" },
  { href: "/workspace/memory", label: "Memory" },
  { href: "/workspace/agents", label: "Assistants" },
  { href: "/workspace/agents/builder", label: "Assistant Builder" },
  { href: "/workspace/approvals", label: "Approvals" },
  { href: "/workspace/integrations", label: "Integrations" },
  { href: "/workspace/optimization", label: "Optimization" },
  { href: "/workspace/learning", label: "Learning" },
  { href: "/workspace/traceability", label: "Traceability" },
  { href: "/workspace/upgrades", label: "Upgrades" },
  { href: "/workspace/ai", label: "AI Assistant" },
  { href: "/workspace/admin/platform-issues", label: "Platform Issues" },
];

export function visibleNavItems(): NavItem[] {
  return NAV_ITEMS;
}

/** Pages that render their own <h1> (the shared PageTitle stays out of the way). */
const OWN_H1 = new Set(["/workspace/upgrades", "/workspace/analysis", "/workspace/design"]); // analysis/design are owned by their own PRs and already render their section name as a heading

/**
 * Nav label (English key; translate with t()) used as the visible page <h1>, or null when the page
 * has its own h1 / is not a nav section. Longest nav prefix wins, so /projects/<id> shows "Projects"
 * while /workspace/agents/<assistant> (a dedicated page with its own h1) shows none.
 */
export function titleForPath(pathname: string): string | null {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (path === "/" || OWN_H1.has(path)) return null;
  if (path.startsWith("/workspace/agents/") && path !== "/workspace/agents/builder") return null;
  let best: NavItem | null = null;
  for (const item of NAV_ITEMS) {
    if (item.href === "/") continue;
    if (path === item.href || path.startsWith(item.href + "/")) {
      if (!best || item.href.length > best.href.length) best = item;
    }
  }
  return best ? best.label : null;
}
