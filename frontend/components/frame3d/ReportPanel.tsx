"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { EmptyHint, useLatestFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { DxfViewer } from "@/components/cad/DxfViewer";
import { createApprovalRequest, downloadFrame3dExport, fetchFrame3dExportText } from "@/lib/api";
import { buildReportHtml } from "@/lib/frame3d-report";
import { useUiLang } from "@/hooks/useUiLang";

export function ReportPanel() {
  const { t, lang } = useUiLang();
  const { projectId, results, inputs } = useLatestFrame3d();
  const html = useMemo(() => (results ? buildReportHtml(results, null, new Date().toLocaleString()) : null), [results]);
  const [rebar, setRebar] = useState<{ text?: string; error?: string; busy?: boolean } | null>(null);
  async function showRebar() {
    if (!inputs) return;
    setRebar({ busy: true });
    try {
      setRebar({ text: await fetchFrame3dExportText("dxf_rebar", inputs) });
    } catch (e) {
      setRebar({ error: e instanceof Error ? e.message : String(e) });
    }
  }
  const [approval, setApproval] = useState<"idle" | "busy" | "done" | string>("idle");
  async function submitForApproval() {
    if (!projectId || !results) return;
    setApproval("busy");
    try {
      const i = (inputs ?? {}) as Record<string, unknown>;
      const dims = ["stories", "bays_x", "bays_y"].map((k) => i[k]).filter((v) => v !== undefined).join(" / ");
      await createApprovalRequest(projectId, {
        targetAction: "frame3d.design_approval",
        summary: `3D frame analysis + Mabhas 9 design${dims ? ` (stories / bays X / bays Y: ${dims})` : ""} — ${new Date().toLocaleString()}`,
        metadata: { source: "frame3d", inputs: i },
      });
      setApproval("done");
    } catch (e) {
      setApproval(e instanceof Error ? e.message : String(e));
    }
  }
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
          {approval === "done" ? (
            <p className="muted" role="status">
              {t("Sent for approval.")} <Link href="/workspace/approvals">{t("Approvals")}</Link>
            </p>
          ) : approval !== "idle" && approval !== "busy" ? (
            <p className="field-error" role="alert">{approval}</p>
          ) : null}
          <div className="frame3d-actions">
            <button type="button" className="button" disabled={!projectId || approval === "busy" || approval === "done"} onClick={() => void submitForApproval()}>
              {t("Submit for approval")}
            </button>
            <button type="button" className="button" onClick={downloadHtml}>
              {t("Download")} HTML
            </button>
            <button type="button" className="button secondary" onClick={() => document.querySelector<HTMLIFrameElement>(".report-frame")?.contentWindow?.print()}>
              {t("Print / PDF")}
            </button>
            {inputs
              ? ["e2k", "f2k", "s2k", "dxf_plans", "dxf_3d", "dxf_rebar", "dxf_foundation"].map((f) => (
                  <button key={f} type="button" className="link-button" onClick={() => void downloadFrame3dExport(f, inputs, { e2k: "model.e2k", f2k: "foundation.f2k", s2k: "model.s2k", dxf_plans: "plans.dxf", dxf_3d: "frame3d.dxf", dxf_rebar: "rebar-details.dxf", dxf_foundation: "foundation-details.dxf" }[f]!)}>
                    {f}
                  </button>
                ))
              : null}
          </div>
          <iframe className="report-frame" title={t("Calculation report")} srcDoc={html} />
          <h3>{t("Rebar detailing drawings")}</h3>
          {rebar?.text ? (
            <DxfViewer text={rebar.text} filename="rebar-details.dxf" />
          ) : (
            <button type="button" className="button secondary" disabled={!inputs || rebar?.busy} onClick={() => void showRebar()}>
              {rebar?.busy ? t("Preparing…") : t("Show rebar drawings")}
            </button>
          )}
          {rebar?.error ? <p className="alert error">{rebar.error}</p> : null}
        </>
      )}
    </section>
  );
}
