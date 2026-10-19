// Sidebar navigation. Every page is complete and listed; nothing is hidden.
export type NavItem = { href: string; label: string };

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Chat" },
  { href: "/projects", label: "Projects" },
  { href: "/workspace/model", label: "Model" },
  { href: "/workspace/analysis", label: "Analysis" },
  { href: "/workspace/results", label: "Results" },
  { href: "/workspace/design", label: "Design" },
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
];

export function visibleNavItems(): NavItem[] {
  return NAV_ITEMS;
}
