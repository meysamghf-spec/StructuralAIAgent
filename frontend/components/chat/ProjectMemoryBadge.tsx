"use client";

import { useEffect, useState } from "react";

import { useUiLang } from "@/hooks/useUiLang";
import { getProjectChatMemory, projectMemoryLabel, type ProjectChatMemory } from "@/lib/project-memory";

/** Small indicator: what the assistant remembers from all chats of the selected project (project-scoped only). */
export function ProjectMemoryBadge({ projectId, refreshKey }: { projectId: string | null; refreshKey?: unknown }) {
  const { lang } = useUiLang();
  const fa = lang === "fa";
  const [mem, setMem] = useState<ProjectChatMemory | null>(null);
  useEffect(() => {
    setMem(null);
    if (!projectId) return;
    let live = true;
    getProjectChatMemory(projectId).then((m) => live && setMem(m)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [projectId, refreshKey]);
  if (!projectId) return null;
  return (
    <details className="project-memory-badge muted" dir={fa ? "rtl" : "ltr"} data-testid="project-memory-badge">
      <summary>🧠 {projectMemoryLabel(mem, fa)}</summary>
      <pre style={{ whiteSpace: "pre-wrap", maxHeight: 240, overflow: "auto", fontSize: 12 }} dir="auto">
        {mem?.text || (fa ? "چیزی برای یادآوری نیست." : "Nothing to remember yet.")}
      </pre>
    </details>
  );
}
