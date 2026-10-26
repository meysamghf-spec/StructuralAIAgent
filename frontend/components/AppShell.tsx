"use client";

import { useAuth } from "@/hooks/useAuth";
import Link from "next/link";
import { MainNav } from "@/components/MainNav";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ChatDock } from "@/components/chat/ChatDock";
import { useUiLang } from "@/hooks/useUiLang";
import { useDrawerDismiss } from "@/hooks/useDrawerDismiss";
import { SaiaLogo } from "@/components/brand/SaiaLogo";


const AUTH_PATHS = new Set(["/login", "/register"]);

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const { lang, t, setLang } = useUiLang();
  const isAuthPage = AUTH_PATHS.has(pathname);
  const isChatHome = pathname === "/" && isAuthenticated;
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => setNavOpen(false), [pathname]);
  const swipe = useDrawerDismiss(navOpen, () => setNavOpen(false));

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  if (isAuthPage) {
    return (
      <div className="auth-shell">
        <main className="content auth-content">
          <div className="auth-brand"><SaiaLogo size="lg" /></div>
          {children}
        </main>
      </div>
    );
  }

  if (isChatHome) {
    return <main className="chat-root">{children}</main>;
  }

  return (
    <div className="shell" data-nav-open={navOpen ? "true" : "false"}>
      <header className="mobile-topbar">
        <button
          type="button"
          className="button secondary mobile-nav-toggle"
          aria-label={navOpen ? "Close menu" : "Open menu"}
          aria-expanded={navOpen}
          onClick={() => setNavOpen((v) => !v)}
        >
          {navOpen ? "✕" : "☰"}
        </button>
        <Link href="/" className="mobile-topbar-title" aria-label="SAIA"><SaiaLogo size="sm" tagline={false} /></Link>
      </header>
      <button
        type="button"
        className="mobile-nav-backdrop"
        aria-hidden={!navOpen}
        tabIndex={-1}
        data-open={navOpen ? "true" : "false"}
        onClick={() => setNavOpen(false)}
        {...swipe}
        data-testid="nav-backdrop"
      />
      <aside className="sidebar" data-open={navOpen ? "true" : "false"} data-testid="nav-drawer" {...swipe}>
        <button type="button" className="drawer-close" aria-label="Close menu" data-testid="drawer-close" onClick={() => setNavOpen(false)}>✕</button>
        <div className="brand">
          <Link href="/" className="brand-link" aria-label="SAIA home"><SaiaLogo size="md" /></Link>
          <h1>Engineering Workspace</h1>
        </div>
        <MainNav onNavigate={() => setNavOpen(false)} />
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
