"use client";

import { useAuth } from "@/hooks/useAuth";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Chat" },
  { href: "/projects", label: "Projects" },
  { href: "/workspace/model", label: "Model" },
  { href: "/workspace/files", label: "Files" },
  { href: "/workspace/memory", label: "Memory" },
  { href: "/workspace/agents", label: "Assistants" },
  { href: "/workspace/agents/builder", label: "Assistant Builder" },
  { href: "/workspace/approvals", label: "Approvals" },
  { href: "/workspace/analysis", label: "Analysis" },
  { href: "/workspace/results", label: "Results" },
  { href: "/workspace/design", label: "Design" },
  { href: "/workspace/optimization", label: "Optimization" },
  { href: "/workspace/integrations", label: "Integrations" },
  { href: "/workspace/cad", label: "CAD" },
  { href: "/workspace/validation", label: "Validation" },
  { href: "/workspace/reports", label: "Reports" },
  { href: "/workspace/traceability", label: "Traceability" },
  { href: "/workspace/upgrades", label: "Upgrades" },
  { href: "/workspace/ai", label: "AI Assistant" },
];

const AUTH_PATHS = new Set(["/login", "/register"]);

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const isAuthPage = AUTH_PATHS.has(pathname);
  const isChatHome = pathname === "/" && isAuthenticated;

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  if (isAuthPage) {
    return (
      <div className="auth-shell">
        <main className="content auth-content">{children}</main>
      </div>
    );
  }

  if (isChatHome) {
    return <main className="chat-root">{children}</main>;
  }

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
        <div className="sidebar-auth">
          {isAuthenticated && user ? (
            <>
              <p className="sidebar-auth-label">Signed in</p>
              <p className="sidebar-auth-user">{user.display_name ?? user.email}</p>
              <p className="muted sidebar-auth-email">{user.email}</p>
              <button className="button secondary sidebar-logout" type="button" onClick={handleLogout}>
                Sign out
              </button>
            </>
          ) : (
            <p className="muted">
              <Link href="/login">Sign in</Link>
            </p>
          )}
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
