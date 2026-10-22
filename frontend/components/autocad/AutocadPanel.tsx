"use client";

import { getApiBaseUrl } from "@/lib/api";
import { getAuthHeaders, getUploadAuthHeaders } from "@/lib/auth-session";
import { useEffect, useState } from "react";

type CadJob = {
  id: string;
  kind: "prompt" | "vectorize";
  summary: Record<string, unknown> & { warnings?: string[]; assumptions?: string[] };
  layers: string[];
  review: { status: string; note: string };
  preview_svg: string;
};

async function readError(res: Response): Promise<string> {
  const body = await res.json().catch(() => ({}));
  return body?.error?.message ?? body?.detail ?? `Request failed (${res.status})`;
}

export function AutocadPanel() {
  const [prompt, setPrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [width, setWidth] = useState("");
  const [busy, setBusy] = useState<"" | "prompt" | "upload" | "review">("");
  const [error, setError] = useState("");
  const [job, setJob] = useState<CadJob | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("cad_prompt");
    if (p) setPrompt(p);
  }, []);

  async function run(kind: "prompt" | "upload") {
    setBusy(kind); setError(""); setJob(null);
    try {
      let res: Response;
      if (kind === "prompt") {
        res = await fetch(`${getApiBaseUrl()}/api/v1/autocad/prompt`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAuthHeaders() },
          body: JSON.stringify({ prompt }),
        });
      } else {
        const fd = new FormData();
        fd.append("file", file as File);
        if (width.trim()) fd.append("real_width_m", width.trim());
        res = await fetch(`${getApiBaseUrl()}/api/v1/autocad/vectorize`, {
          method: "POST", headers: { ...getUploadAuthHeaders() }, body: fd,
        });
      }
      if (!res.ok) throw new Error(await readError(res));
      setJob((await res.json()) as CadJob);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function download() {
    if (!job) return;
    const res = await fetch(`${getApiBaseUrl()}/api/v1/autocad/jobs/${job.id}/drawing.dxf`, { headers: { ...getAuthHeaders() } });
    if (!res.ok) { setError(await readError(res)); return; }
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = `structuralai-${job.id.slice(0, 8)}.dxf`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  async function review(decision: "accept" | "flag") {
    if (!job) return;
    setBusy("review");
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/v1/autocad/jobs/${job.id}/review`, {
        method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ decision, note }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const meta = await res.json();
      setJob({ ...job, review: meta.review });
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(""); }
  }

  const s = job?.summary ?? {};
  return (
    <section className="card autocad-panel" id="autocad" data-testid="autocad-panel">
      <h2>AutoCAD (DXF)</h2>
      <p className="muted">Turn a prompt or a plan photo/PDF into a layered DXF. Works without a project.</p>
      <div className="grid cards-2">
        <div className="autocad-box">
          <h3>Prompt → drawing</h3>
          <textarea
            data-testid="cad-prompt" rows={3} dir="auto" value={prompt}
            placeholder="e.g. 3-storey residential building 12x20 m / ساختمان مسکونی ۴ طبقه ۱۲ در ۲۰ متر"
            onChange={(e) => setPrompt(e.target.value)}
          />
          <button type="button" className="button" data-testid="cad-generate" disabled={prompt.trim().length < 3 || !!busy} onClick={() => run("prompt")}>
            {busy === "prompt" ? "Generating…" : "Generate DXF"}
          </button>
          {prompt.trim().length < 3 ? <p className="field-hint">Describe the building to enable.</p> : null}
        </div>
        <div className="autocad-box">
          <h3>PDF or image → DXF</h3>
          <input
            data-testid="cad-file" type="file" accept="application/pdf,image/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <label className="field-hint">
            Real drawing width in m (optional)
            <input type="number" inputMode="decimal" min="0" step="0.1" value={width} onChange={(e) => setWidth(e.target.value)} />
          </label>
          <button type="button" className="button" data-testid="cad-vectorize" disabled={!file || !!busy} onClick={() => run("upload")}>
            {busy === "upload" ? "Converting…" : "Convert to DXF"}
          </button>
          {!file ? <p className="field-hint">Pick a PDF, or take/choose a photo of a plan.</p> : null}
        </div>
      </div>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {job ? (
        <div className="autocad-result" data-testid="cad-result">
          <div className="autocad-preview" dangerouslySetInnerHTML={{ __html: job.preview_svg }} />
          <div className="autocad-actions">
            <button type="button" className="button" data-testid="cad-download" onClick={download}>Download DXF</button>
            <span className="chip">Sheet {String(s.sheet ?? "")}</span>
            {job.kind === "vectorize" ? <span className="chip" data-testid="cad-review-status">Review: {job.review.status}</span> : null}
          </div>
          {job.kind === "vectorize" ? (
            <div className="autocad-review">
              <p className="field-hint">Engineer review: accept before this drawing is used as a model.</p>
              <input type="text" placeholder="Review note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="autocad-actions">
                <button type="button" className="button" data-testid="cad-accept" disabled={!!busy} onClick={() => review("accept")}>Accept</button>
                <button type="button" className="button secondary" data-testid="cad-flag" disabled={!!busy} onClick={() => review("flag")}>Flag</button>
              </div>
            </div>
          ) : null}
          <details className="meta-summary">
            <summary>Details</summary>
            <ul>
              {Object.entries(s).filter(([k]) => !["warnings", "assumptions"].includes(k)).map(([k, v]) => (
                <li key={k}>{k}: {Array.isArray(v) ? v.join(" × ") : String(v)}</li>
              ))}
              <li>layers: {job.layers.join(", ")}</li>
              {(s.warnings ?? []).map((w) => <li key={w}>⚠ {w}</li>)}
              {(s.assumptions ?? []).map((w) => <li key={w}>{w}</li>)}
            </ul>
          </details>
        </div>
      ) : null}
    </section>
  );
}
