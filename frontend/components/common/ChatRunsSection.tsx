"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AutocadDrawingCard } from "@/components/autocad/AutocadDrawingCard";
import { SectionErrorBoundary } from "@/components/common/SectionErrorBoundary";
import { DownloadsPanel, IncompleteInputsNote, missingInputs } from "@/components/frame3d/DownloadsPanel";
import { listProjectChatRuns, type ChatRun } from "@/lib/chat-runs";
import { NEUTRAL_TITLE, RUNS_TITLE_FA } from "@/lib/runs-titles";
import { useUiLang } from "@/hooks/useUiLang";
import { inputLabel, missingGeometry } from "@/lib/input-labels";
import { getCurrentProjectId, PROJECT_EVENT, projectChatHref } from "@/lib/current-project";
import { ensureCurrentProject } from "@/lib/ensure-project";

const KIND_LABEL: Record<string, { en: string; fa: string }> = {
  frame3d_analysis: { en: "3D frame analysis", fa: "تحلیل قاب سه‌بعدی" },
  aci_rc_beam: { en: "RC beam", fa: "تیر بتنی" },
  demo_rc_beam: { en: "Beam calc", fa: "محاسبهٔ تیر" },
  frame_optimization: { en: "Optimization", fa: "بهینه‌سازی" },
  autocad: { en: "AutoCAD drawing", fa: "نقشهٔ اتوکد" },
  agent_execution: { en: "Assistant run", fa: "اجرای دستیار" },
};


const runKey = (r: ChatRun) => r.message_id + r.kind;
/** A frame run that stopped at "missing required input" (or whose stored geometry is incomplete) and was not fixed inline yet. */
const isIncomplete = (r: ChatRun, fixed?: Record<string, unknown>) =>
  r.kind === "frame3d_analysis" && !fixed && (missingInputs(r.inputs).length > 0 || /missing|incomplete/i.test(String(r.status ?? "")));

/** Runs made in chat for the selected project — shown on Results, Optimization, Validation, Traceability, Files. */
export function ChatRunsSection(props: { kinds?: string[]; excludeKinds?: string[]; title?: string }) {
  return (
    <SectionErrorBoundary label="Runs">
      <ChatRunsSectionInner {...props} />
    </SectionErrorBoundary>
  );
}

function ChatRunsSectionInner({ kinds, excludeKinds, title = NEUTRAL_TITLE }: { kinds?: string[]; excludeKinds?: string[]; title?: string }) {
  const { lang } = useUiLang();
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const [fixed, setFixed] = useState<Record<string, Record<string, unknown>>>({});
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

  const shown = (runs ?? []).filter((r) => (!kinds || kinds.includes(r.kind)) && !excludeKinds?.includes(r.kind));

  return (
    <section className="card chat-runs" data-testid="chat-runs" dir={lang === "fa" ? "rtl" : "ltr"} lang={lang}>
      <h3>{lang === "fa" ? RUNS_TITLE_FA[title] ?? title : title}</h3>
      {!projectId ? <p className="muted">{tx("Select a project to see its runs.", "برای دیدن اجراها یک پروژه انتخاب کنید.")}</p> : null}
      {error ? <p className="alert error">{error}</p> : null}
      {projectId && runs === null && !error ? <p className="muted">{tx("Loading…", "در حال بارگذاری…")}</p> : null}
      {projectId && runs && shown.length === 0 ? (
        <p className="muted">{tx("No runs in this project yet.", "هنوز اجرایی در این پروژه نیست.")}</p>
      ) : null}
      <ul className="chat-runs-list">
        {shown.map((r) => (
          <li key={r.message_id + r.kind} className="chat-run-item">
            <SectionErrorBoundary label={r.label || "Run"}>
            <div className="chat-run-head">
              <span className="chat-progress-badge">{KIND_LABEL[r.kind]?.[lang] ?? r.kind}</span>
              <strong dir="auto">{r.label}</strong>
            </div>
            <p className="muted chat-run-meta">
              {(r.created_at ? new Date(r.created_at).toLocaleString() : "")} · {r.status}
              {Object.entries(r.summary || {})
                .slice(0, 4)
                .map(([k, v]) => ` · ${inputLabel(k, lang)}: ${typeof v === "number" ? Math.round(v * 1000) / 1000 : v}`)
                .join("")}
            </p>
            {isIncomplete(r, fixed[runKey(r)]) ? (
              <IncompleteInputsNote
                missing={missingGeometry(r.inputs ?? {})}
                lang={lang}
                inputs={r.inputs}
                projectId={projectId}
                onDone={(_p, merged) => setFixed((f) => ({ ...f, [runKey(r)]: merged }))}
              />
            ) : null}
            <div className="chat-message-actions">
              <Link className="button secondary chat-action-link" href={projectChatHref(projectId!)}>
                {tx("Open chat", "باز کردن گفتگو")}
              </Link>
              {(r.inputs && !isIncomplete(r, fixed[runKey(r)])) || (r.kind === "autocad" && r.job_id) ? (
                <button
                  className="button chat-action-link"
                  type="button"
                  aria-expanded={open === r.message_id + r.kind}
                  onClick={() => setOpen(open === r.message_id + r.kind ? null : r.message_id + r.kind)}
                >
                  {open === r.message_id + r.kind
                    ? tx("Hide results", "بستن نتایج")
                    : r.kind === "autocad"
                      ? tx("Open drawing", "باز کردن نقشه")
                      : tx("Results & downloads", "نتایج و دانلودها")}
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
                ) : /fail|error/i.test(String(r.status ?? "")) && !fixed[runKey(r)] ? (
                  <IncompleteInputsNote missing={missingInputs(r.inputs)} lang={lang} inputs={r.inputs} projectId={projectId} />
                ) : (
                  <DownloadsPanel inputs={fixed[runKey(r)] ?? r.inputs} projectId={projectId} optimization={r.optimization} />
                )}
              </div>
            ) : null}
            </SectionErrorBoundary>
          </li>
        ))}
      </ul>
    </section>
  );
}
