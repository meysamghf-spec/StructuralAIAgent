"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AutocadDrawingCard } from "@/components/autocad/AutocadDrawingCard";
import { DownloadsPanel } from "@/components/frame3d/DownloadsPanel";
import { listProjectChatRuns, type ChatRun } from "@/lib/chat-runs";
import { getCurrentProjectId, PROJECT_EVENT, projectChatHref } from "@/lib/current-project";
import { ensureCurrentProject } from "@/lib/ensure-project";

const KIND_LABEL: Record<string, string> = {
  frame3d_analysis: "3D frame analysis",
  aci_rc_beam: "RC beam",
  demo_rc_beam: "Beam calc",
  frame_optimization: "Optimization",
  autocad: "AutoCAD drawing",
  agent_execution: "Assistant run",
};

/** Runs made in chat for the selected project — shown on Results, Optimization, Validation, Traceability, Files. */
export function ChatRunsSection({ kinds, title = "Runs from chat" }: { kinds?: string[]; title?: string }) {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [runs, setRuns] = useState<ChatRun[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => {
      const pid = getCurrentProjectId();
      setProjectId(pid);
      setRuns(null);
      setError("");
      if (!pid) {
        void ensureCurrentProject().then((id) => {
          if (!id) setRuns([]);
        });
        return;
      }
      listProjectChatRuns(pid, true)
        .then(setRuns)
        .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    return () => window.removeEventListener(PROJECT_EVENT, sync);
  }, []);

  const shown = (runs ?? []).filter((r) => !kinds || kinds.includes(r.kind));

  return (
    <section className="card chat-runs" data-testid="chat-runs">
      <h3>{title}</h3>
      {!projectId ? <p className="muted">Select a project to see its chat runs.</p> : null}
      {error ? <p className="alert error">{error}</p> : null}
      {projectId && runs === null && !error ? <p className="muted">Loading…</p> : null}
      {projectId && runs && shown.length === 0 ? (
        <p className="muted">No runs from chat in this project yet.</p>
      ) : null}
      <ul className="chat-runs-list">
        {shown.map((r) => (
          <li key={r.message_id + r.kind} className="chat-run-item">
            <div className="chat-run-head">
              <span className="chat-progress-badge">{KIND_LABEL[r.kind] ?? r.kind}</span>
              <strong dir="auto">{r.label}</strong>
            </div>
            <p className="muted chat-run-meta">
              {new Date(r.created_at).toLocaleString()} · {r.status}
              {Object.entries(r.summary || {})
                .slice(0, 4)
                .map(([k, v]) => ` · ${k.replace(/_/g, " ")}: ${typeof v === "number" ? Math.round(v * 1000) / 1000 : v}`)
                .join("")}
            </p>
            <div className="chat-message-actions">
              <Link className="button secondary chat-action-link" href={projectChatHref(projectId!)}>
                Open chat
              </Link>
              {r.inputs || (r.kind === "autocad" && r.job_id) ? (
                <button
                  className="button chat-action-link"
                  type="button"
                  aria-expanded={open === r.message_id + r.kind}
                  onClick={() => setOpen(open === r.message_id + r.kind ? null : r.message_id + r.kind)}
                >
                  {open === r.message_id + r.kind ? "Hide results" : r.kind === "autocad" ? "Open drawing" : "Results & downloads"}
                </button>
              ) : null}
            </div>
            {open === r.message_id + r.kind ? (
              <div className="inline-panel" data-testid="chat-run-inline">
                {r.kind === "autocad" && r.job_id ? (
                  <AutocadDrawingCard
                    jobId={r.job_id}
                    kind="prompt"
                    title={r.label}
                    filename={r.filename || `autocad-${r.job_id.slice(0, 8)}.dxf`}
                    layers={[]}
                    review={{ status: r.status, note: "" }}
                  />
                ) : (
                  <DownloadsPanel inputs={r.inputs} projectId={projectId} optimization={r.optimization} />
                )}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
