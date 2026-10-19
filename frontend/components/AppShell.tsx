"use client";

import { useAuth } from "@/hooks/useAuth";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { ChatDock } from "@/components/chat/ChatDock";
import { useUiLang } from "@/hooks/useUiLang";
import { visibleNavItems } from "@/lib/nav";


const AUTH_PATHS = new Set(["/login", "/register"]);

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const { lang, t, setLang } = useUiLang();
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
          {visibleNavItems().map((item) => {
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
                {t(item.label)}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-lang">
          <span>{t("Language")}:</span>
          <button type="button" className={lang === "en" ? "lang-btn active" : "lang-btn"} onClick={() => setLang("en")}>EN</button>
          <button type="button" className={lang === "fa" ? "lang-btn active" : "lang-btn"} onClick={() => setLang("fa")}>فا</button>
        </div>
        <div className="sidebar-auth">
          {isAuthenticated && user ? (
            <>
              <p className="sidebar-auth-label">{t("Signed in")}</p>
              <p className="sidebar-auth-user">{user.display_name ?? user.email}</p>
              <p className="muted sidebar-auth-email">{user.email}</p>
              <button className="button secondary sidebar-logout" type="button" onClick={handleLogout}>
                {t("Sign out")}
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
      {isAuthenticated ? <ChatDock /> : null}
    </div>
  );
}
