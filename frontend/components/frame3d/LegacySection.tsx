"use client";

import type { ReactNode } from "react";

import { useUiLang } from "@/hooks/useUiLang";

/** Older PEM-based workspace tools, kept but collapsed under the in-house 3D frame panel. */
export function LegacySection({ label, children }: { label: string; children: ReactNode }) {
  const { t } = useUiLang();
  return (
    <details className="legacy-section" data-section={label}>
      <summary>{t(label === "model" ? "Advanced: project engineering model (legacy)" : "Advanced: legacy workspace tools")}</summary>
      {children}
    </details>
  );
}
