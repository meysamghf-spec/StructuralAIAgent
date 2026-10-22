"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUiLang } from "@/hooks/useUiLang";
import { visibleNavItems } from "@/lib/nav";

/** The one navigation menu used on every page (desktop sidebar, mobile drawer, Chat). */
export function MainNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname() ?? "/";
  const { t } = useUiLang();
  return (
    <nav className="nav main-nav" aria-label="Main">
      {visibleNavItems().map((item) => {
        const active =
          item.href === "/"
            ? pathname === "/"
            : pathname === item.href ||
              (pathname.startsWith(`${item.href}/`) &&
                !visibleNavItems().some((o) => o.href !== item.href && o.href.startsWith(`${item.href}/`) && pathname.startsWith(o.href)));
        return (
          <Link key={item.href} href={item.href} className={active ? "nav-link active" : "nav-link"} aria-current={active ? "page" : undefined} onClick={onNavigate}>
            {t(item.label)}
          </Link>
        );
      })}
    </nav>
  );
}
