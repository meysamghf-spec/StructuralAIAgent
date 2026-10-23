"use client";

import { useEffect, useState } from "react";

import { DownloadsPanel } from "@/components/frame3d/DownloadsPanel";
import { useLatestFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { fetchFrame3dExportText } from "@/lib/api";

const FORMAT: Record<string, { fmt: string; label: string }> = {
  ETABS: { fmt: "e2k", label: "ETABS .e2k" },
  SAP2000: { fmt: "s2k", label: "SAP2000 .s2k" },
  SAFE: { fmt: "f2k", label: "SAFE .f2k" },
};

/** Inline summary + model preview + downloads under an integration card (no navigation away). */
export function SolverInlinePanel({ software }: { software: string }) {
  const { projectId, inputs, results } = useLatestFrame3d();
  const meta = FORMAT[software.toUpperCase()];
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!inputs || !meta) return;
    let live = true;
    setText(null);
    fetchFrame3dExportText(meta.fmt, inputs)
      .then((t) => live && setText(t))
      .catch((e) => live && setErr(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [inputs, meta]);
  if (!meta) return null;
  const lines = text ? text.split(/\r?\n/) : [];
  return (
    <div className="inline-panel solver-inline" data-testid={`solver-inline-${meta.fmt}`}>
      {!inputs ? (
        <p className="muted">No 3D frame analysis in this project yet — run one in chat or on the Model page.</p>
      ) : (
        <>
          <p className="muted">
            {meta.label} from the latest frame
            {results?.fields?.length ? ": " + results.fields.slice(0, 4).map((f) => `${f.label} ${f.value}${f.unit ? " " + f.unit : ""}`).join(" · ") : ""}
            {text ? ` · ${lines.length} lines` : ""}
          </p>
          {err ? <p className="alert error">{err}</p> : null}
          {text ? (
            <pre className="solver-preview" dir="ltr">{lines.slice(0, 60).join("\n")}{lines.length > 60 ? "\n…" : ""}</pre>
          ) : !err ? (
            <p className="muted">Loading preview…</p>
          ) : null}
          <DownloadsPanel inputs={inputs} projectId={projectId} groups={software.toUpperCase() === "SAFE" ? ["models", "foundation"] : ["models", "analysis"]} />
        </>
      )}
    </div>
  );
}
