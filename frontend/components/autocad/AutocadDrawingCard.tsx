"use client";

import { downloadAutocadDxf, fetchAutocadPreview, reviewAutocadJob } from "@/lib/autocad";
import { useEffect, useState } from "react";

type Props = {
  jobId: string;
  title: string;
  filename: string;
  kind: "prompt" | "vectorize";
  layers: string[];
  review: { status: string; note: string };
  savedToProject?: boolean;
};

/** Preview + DXF download + engineer review for one AutoCAD job (chat result card and CAD page). */
export function AutocadDrawingCard({ jobId, title, filename, kind, layers, review, savedToProject }: Props) {
  const [svg, setSvg] = useState<string | null>(null);
  const [status, setStatus] = useState(review.status);
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchAutocadPreview(jobId).then(setSvg).catch((e) => setErr(String(e?.message ?? e)));
  }, [jobId]);

  async function decide(d: "accept" | "flag") {
    setBusy(true);
    setErr("");
    try {
      setStatus((await reviewAutocadJob(jobId, d, note)).review.status);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="autocad-card" data-testid="autocad-card">
      <div className="autocad-card-head">
        <strong>{title}</strong>
        <span className={`chat-progress-badge${status === "flagged" ? " warning" : ""}`}>
          {status === "pending" ? "Needs review" : status === "accepted" ? "Accepted" : status === "flagged" ? "Flagged" : "Ready"}
        </span>
      </div>
      <div className="autocad-card-preview">
        {svg ? <div dangerouslySetInnerHTML={{ __html: svg }} /> : <span className="muted">Loading preview…</span>}
      </div>
      <div className="autocad-card-actions">
        <button type="button" className="button" onClick={() => void downloadAutocadDxf(jobId, filename)}>
          Download {filename}
        </button>
        {kind === "vectorize" && status === "pending" ? (
          <>
            <input
              className="autocad-note"
              placeholder="Note (optional)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <button type="button" className="button secondary" disabled={busy} onClick={() => void decide("accept")}>
              Accept
            </button>
            <button type="button" className="button secondary" disabled={busy} onClick={() => void decide("flag")}>
              Flag
            </button>
          </>
        ) : null}
      </div>
      <p className="muted autocad-card-meta">
        {layers.length} layers{savedToProject ? " · saved to project files" : ""}
      </p>
      {err ? <p className="alert error">{err}</p> : null}
    </div>
  );
}
