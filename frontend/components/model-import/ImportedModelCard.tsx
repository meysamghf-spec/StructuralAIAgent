"use client";

// Results / Design pages: the latest analysed imported model of the current project (read-only).
import Link from "next/link";
import { useEffect, useState } from "react";

import { useUiLang } from "@/hooks/useUiLang";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import { latestImport, type ImportState } from "@/lib/model-import";

import { ImportResults } from "./ImportResults";

export function ImportedModelCard({ mode }: { mode: "results" | "design" }) {
  const { lang } = useUiLang();
  const fa = lang === "fa";
  const [projectId, setProjectId] = useState<string | null>(null);
  const [state, setState] = useState<ImportState | null>(null);
  useEffect(() => {
    const sync = () => setProjectId(getCurrentProjectId());
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    return () => window.removeEventListener(PROJECT_EVENT, sync);
  }, []);
  useEffect(() => {
    if (!projectId) { setState(null); return; }
    latestImport(projectId).then(setState).catch(() => setState(null));
  }, [projectId]);
  if (!state?.analysis) return null;
  const title = fa ? `مدل واردشده: ${state.model.filename ?? ""}` : `Imported model: ${state.model.filename ?? ""}`;
  return (
    <section dir={fa ? "rtl" : "ltr"} data-testid={`imported-model-${mode}`} style={{ border: "1px solid rgba(127,127,127,0.4)", borderRadius: 10, padding: 12, marginBottom: 16, maxWidth: "100%", overflowX: "hidden" }}>
      <h2 style={{ margin: 0, fontSize: 17 }}>{title}</h2>
      <p style={{ margin: "2px 0 0", fontSize: 12, opacity: 0.75 }}>
        {fa ? "نتایج از موتور SAIA؛ برای ویرایش و تحلیل دوباره به صفحه‌ی مدل بروید." : "Results from the SAIA engine; edit and re-analyse on the Model page."}{" "}
        <Link href="/workspace/model" style={{ color: "#3b82f6" }}>{fa ? "صفحه‌ی مدل" : "Model page"}</Link>
      </p>
      <ImportResults a={state.analysis} fa={fa} mode={mode} />
    </section>
  );
}
