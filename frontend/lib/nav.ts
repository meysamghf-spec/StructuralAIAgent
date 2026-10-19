// Sidebar navigation. Pages marked `hidden` are stubs / not usable end-to-end yet: their code stays,
// they are reachable by URL, and they reappear in the menu with NEXT_PUBLIC_SHOW_ALL_PAGES=1.
export type NavItem = { href: string; label: string; hidden?: boolean };

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Chat" },
  { href: "/projects", label: "Projects" },
  { href: "/workspace/model", label: "Model" },
  { href: "/workspace/analysis", label: "Analysis" },
  { href: "/workspace/results", label: "Results" },
  { href: "/workspace/design", label: "Design" },
  { href: "/workspace/cad", label: "CAD" },
  { href: "/workspace/reports", label: "Reports" },
  { href: "/workspace/validation", label: "Validation", hidden: true },
  { href: "/workspace/files", label: "Files" },
  { href: "/workspace/memory", label: "Memory", hidden: true },
  { href: "/workspace/agents", label: "Assistants", hidden: true },
  { href: "/workspace/agents/builder", label: "Assistant Builder", hidden: true },
  { href: "/workspace/approvals", label: "Approvals" },
  { href: "/workspace/integrations", label: "Integrations", hidden: true },
  { href: "/workspace/optimization", label: "Optimization", hidden: true },
  { href: "/workspace/learning", label: "Learning", hidden: true },
  { href: "/workspace/traceability", label: "Traceability", hidden: true },
  { href: "/workspace/upgrades", label: "Upgrades", hidden: true },
  { href: "/workspace/ai", label: "AI Assistant", hidden: true },
];

export function visibleNavItems(showAll: boolean = process.env.NEXT_PUBLIC_SHOW_ALL_PAGES === "1"): NavItem[] {
  return NAV_ITEMS.filter((item) => showAll || !item.hidden);
}
