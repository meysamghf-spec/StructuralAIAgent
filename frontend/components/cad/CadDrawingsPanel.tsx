"use client";

import { useEffect, useState } from "react";

import { DxfViewer } from "@/components/cad/DxfViewer";
import { EmptyHint, useLatestFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { downloadFrame3dExport, fetchFrame3dExportText } from "@/lib/api";
import { useUiLang } from "@/hooks/useUiLang";

const DRAWINGS = [
  { format: "dxf_plans", filename: "plans.dxf", label: "Story plans + foundation plan" },
  { format: "dxf_3d", filename: "frame3d.dxf", label: "3D wireframe" },
  { format: "dxf_rebar", filename: "rebar-details.dxf", label: "Rebar detailing + bar schedule" },
  { format: "dxf_foundation", filename: "foundation-details.dxf", label: "Foundation detailing (plan, sections, schedule)" },
];
const DOWNLOADS = [
  { format: "dxf_plans", filename: "plans.dxf" },
  { format: "dxf_3d", filename: "frame3d.dxf" },
  { format: "dxf_rebar", filename: "rebar-details.dxf" },
  { format: "dxf_foundation", filename: "foundation-details.dxf" },
  { format: "e2k", filename: "model.e2k" },
  { format: "f2k", filename: "foundation.f2k" },
  { format: "s2k", filename: "model.s2k" },
];

export function CadDrawingsPanel() {
  const { t, lang } = useUiLang();
  const { projectId, inputs } = useLatestFrame3d();
  const [which, setWhich] = useState(DRAWINGS[0].format);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = inputs ? JSON.stringify(inputs) : "";

  useEffect(() => {
    if (!inputs) return;
    setText(null);
    setError(null);
    fetchFrame3dExportText(which, inputs)
      .then(setText)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [which, key]);

  const drawing = DRAWINGS.find((d) => d.format === which)!;
  return (
    <section className="panel" dir={lang === "fa" ? "rtl" : "ltr"}>
      <h2>{t("Project drawings")}</h2>
      {!inputs ? (
        <EmptyHint projectId={projectId} text={t("No drawings yet: analyse a 3D frame in the chat or on the Model page.")} />
      ) : (
        <>
          <div className="frame3d-actions">
            {DRAWINGS.map((d) => (
              <button key={d.format} type="button" className={which === d.format ? "button" : "button secondary"} onClick={() => setWhich(d.format)}>
                {t(d.label)}
              </button>
            ))}
            <span className="muted">{t("Downloads")}:</span>
            {DOWNLOADS.map((d) => (
              <button key={d.format} type="button" className="link-button" onClick={() => void downloadFrame3dExport(d.format, inputs, d.filename)}>
                {d.filename}
              </button>
            ))}
          </div>
          {error ? <p className="alert error">{error}</p> : null}
          {text ? <DxfViewer text={text} filename={drawing.filename} /> : !error ? <p className="muted">{t("Preparing…")}</p> : null}
        </>
      )}
    </section>
  );
}
