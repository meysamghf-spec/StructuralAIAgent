"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { SaiaLogo } from "@/components/brand/SaiaLogo";
import { useUiLang } from "@/hooks/useUiLang";

/**
 * Public page chrome (no gate/login). Both languages are rendered into the HTML so crawlers see them;
 * the visitor's language choice just hides the other one after hydration.
 */
export function PublicPage({ en, fa }: { en: ReactNode; fa: ReactNode }) {
  const { lang, setLang } = useUiLang();
  return (
    <div className="public-shell">
      <header className="public-header">
        <Link href="/about" aria-label="SAIA"><SaiaLogo size="md" /></Link>
        <div className="sidebar-lang">
          <button type="button" className={lang === "en" ? "lang-btn active" : "lang-btn"} onClick={() => setLang("en")}>EN</button>
          <button type="button" className={lang === "fa" ? "lang-btn active" : "lang-btn"} onClick={() => setLang("fa")}>فا</button>
        </div>
      </header>
      <main className="public-main">
        <article lang="en" dir="ltr" hidden={lang !== "en"} className="public-doc">{en}</article>
        <article lang="fa" dir="rtl" hidden={lang !== "fa"} className="public-doc">{fa}</article>
      </main>
      <footer className="public-footer">
        <nav aria-label="Legal">
          <Link href="/about">{lang === "fa" ? "درباره" : "About"}</Link>
          <Link href="/privacy">{lang === "fa" ? "حریم خصوصی" : "Privacy Policy"}</Link>
          <Link href="/terms">{lang === "fa" ? "شرایط استفاده" : "Terms of Service"}</Link>
          <a href="mailto:meysam.ghf@gmail.com">meysam.ghf@gmail.com</a>
        </nav>
        <p className="muted">© SAIA</p>
      </footer>
    </div>
  );
}
