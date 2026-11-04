"use client";

import { useEffect, useState } from "react";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";

/** The active project id, kept in sync with the project switcher (sidebar, top bar, page selectors). */
export function useActiveProjectId(): string | null {
  const [id, setId] = useState<string | null>(null);
  useEffect(() => {
    setId(getCurrentProjectId());
    const onChange = (e: Event) => setId((e as CustomEvent<string | null>).detail ?? getCurrentProjectId());
    const onStorage = (e: StorageEvent) => { if (e.key === "sa.currentProjectId") setId(getCurrentProjectId()); };
    window.addEventListener(PROJECT_EVENT, onChange);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(PROJECT_EVENT, onChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  return id;
}
