"use client";

import { useMemo } from "react";

import { EmptyHint, useLatestFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { downloadFrame3dExport } from "@/lib/api";
import { buildReportHtml } from "@/lib/frame3d-report";
import { useUiLang } from "@/hooks/useUiLang";

export function ReportPanel() {
  const { t, lang } = useUiLang();
  const { projectId, results, inputs } = useLatestFrame3d();
  const html = useMemo(() => (results ? buildReportHtml(results, null, new Date().toLocaleString()) : null), [results]);
  function downloadHtml() {
    if (!html) return;
    const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "frame3d-report.html";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="panel" dir={lang === "fa" ? "rtl" : "ltr"}>
      <h2>{t("Calculation report")}</h2>
      {!html ? (
        <EmptyHint projectId={projectId} text={t("No report yet: analyse a 3D frame in the chat or on the Model page.")} />
      ) : (
        <>
          <div className="frame3d-actions">
            <button type="button" className="button" onClick={downloadHtml}>
              {t("Download")} HTML
            </button>
            <button type="button" className="button secondary" onClick={() => document.querySelector<HTMLIFrameElement>(".report-frame")?.contentWindow?.print()}>
              {t("Print / PDF")}
            </button>
            {inputs
              ? ["e2k", "f2k", "dxf_plans", "dxf_3d"].map((f) => (
                  <button key={f} type="button" className="link-button" onClick={() => void downloadFrame3dExport(f, inputs, { e2k: "model.e2k", f2k: "foundation.f2k", dxf_plans: "plans.dxf", dxf_3d: "frame3d.dxf" }[f]!)}>
                    {f}
                  </button>
                ))
              : null}
          </div>
          <iframe className="report-frame" title={t("Calculation report")} srcDoc={html} />
        </>
      )}
    </section>
  );
}
