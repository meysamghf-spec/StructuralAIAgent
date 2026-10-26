"use client";

import { AutocadDrawingCard } from "@/components/autocad/AutocadDrawingCard";
import { downloadStructuralSetPdf, type StructuralSet } from "@/lib/structural-set";
import { useState } from "react";

/** One structural drawing set: sheet list + per-sheet preview (pan/zoom) + DXF downloads + combined PDF. */
export function StructuralSetView({ set: rawSet, compact = false }: { set: StructuralSet; compact?: boolean }) {
  const set: StructuralSet = {
    ...rawSet,
    sheets: Array.isArray(rawSet?.sheets) ? rawSet.sheets : [],
    notes: Array.isArray(rawSet?.notes) ? rawSet.notes : [],
  };
  const [open, setOpen] = useState<string | null>(compact ? null : set.sheets[0]?.job_id ?? null);
  const [err, setErr] = useState("");
  const current = set.sheets.find((s) => s.job_id === open);
  return (
    <div className="structural-set" data-testid="structural-set">
      <div className="structural-set-head">
        <strong>Structural drawing set · نقشه‌های اجرایی سازه</strong>
        <span className="muted">{set.sheets.length} sheets{set.created_at ? ` · ${new Date(set.created_at).toLocaleString()}` : ""}</span>
      </div>
      {set.frame ? (
        <p className="muted structural-set-meta">
          {set.frame.storeys} storeys · {set.frame.bays_x}×{set.frame.bay_x_m} m (x) · {set.frame.bays_y}×{set.frame.bay_y_m} m (y) · h {set.frame.storey_height_m} m
        </p>
      ) : null}
      <ul className="structural-sheet-list">
        {set.sheets.map((s) => (
          <li key={s.job_id}>
            <button
              type="button"
              className={`structural-sheet-btn${open === s.job_id ? " active" : ""}`}
              onClick={() => setOpen(open === s.job_id ? null : s.job_id)}
              aria-expanded={open === s.job_id}
            >
              <span className="structural-sheet-no">{s.sheet_no}</span>
              <span className="structural-sheet-title">
                {s.title}
                <span className="muted" dir="rtl"> {s.title_fa}</span>
              </span>
              <span className="muted structural-sheet-scale">{s.scale}</span>
            </button>
          </li>
        ))}
      </ul>
      {set.notes.length ? (
        <ul className="structural-set-notes">
          {set.notes.map((n) => (
            <li key={n} className="muted">⚠ {n}</li>
          ))}
        </ul>
      ) : null}
      <div className="autocad-card-actions">
        {set.pdf ? (
          <button
            type="button"
            className="button"
            onClick={() => void downloadStructuralSetPdf(set.id).catch((e) => setErr(e instanceof Error ? e.message : String(e)))}
          >
            Download combined PDF
          </button>
        ) : null}
      </div>
      {err ? <p className="alert error">{err}</p> : null}
      {current ? (
        <AutocadDrawingCard
          key={current.job_id}
          jobId={current.job_id}
          kind="prompt"
          title={`${current.sheet_no} — ${current.title}`}
          filename={`${current.sheet_no}.dxf`}
          layers={[]}
          review={{ status: "not_required", note: "" }}
          savedToProject={!!current.file_id}
        />
      ) : null}
    </div>
  );
}
