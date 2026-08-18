"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
  { href: "/workspace/memory", label: "Memory" },
  { href: "/workspace/files", label: "Files" },
  { href: "/workspace/analysis", label: "Analysis" },
  { href: "/workspace/design", label: "Design" },
  { href: "/workspace/validation", label: "Validation" },
  { href: "/workspace/agents", label: "Agents" },
  { href: "/workspace/ai", label: "AI Assistant" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <p className="brand-eyebrow">StructuralAIAgent</p>
          <h1>Engineering Workspace</h1>
        </div>
        <nav className="nav">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? "nav-link active" : "nav-link"}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
