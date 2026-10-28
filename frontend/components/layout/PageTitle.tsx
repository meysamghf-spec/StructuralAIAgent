"use client";

import { usePathname } from "next/navigation";

import { useUiLang } from "@/hooks/useUiLang";
import { titleForPath } from "@/lib/nav";

/** Shared visible page title: the section name (same label as the nav) as the page's single <h1>. */
export function PageTitle() {
  const pathname = usePathname() ?? "/";
  const { t } = useUiLang();
  const label = titleForPath(pathname);
  if (!label) return null;
  return (
    <h1 className="page-title" data-testid="page-title">
      {t(label)}
    </h1>
  );
}
