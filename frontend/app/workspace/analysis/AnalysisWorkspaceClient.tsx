"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { AnalysisKpis, AnalysisSections } from "@/components/analysis/AnalysisResultsView";
import { runFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { useUiLang } from "@/hooks/useUiLang";
import {
  inputLabel,
  loadLastRun,
  makeAnalysisT,
  missingModelInputs,
  saveLastRun,
  summarizeAnalysis,
  unitSystemLabel,
  type LastRun,
} from "@/lib/analysis-results";
import { hydrateFrame3dFromServer } from "@/lib/chat-runs";
import { PROJECT_EVENT } from "@/lib/current-project";
import {
  FRAME3D_EVENT,
  loadFrame3dInputs,
  loadFrame3dPayload,
  saveFrame3dInputs,
  saveFrame3dPayload,
} from "@/lib/frame3d-store";
import "@/components/analysis/analysis.css";

type RunState = { kind: "idle" } | { kind: "running" } | { kind: "ok" } | { kind: "error"; message: string };

/** `viewer` (the 3D frame section) is rendered right under the run banner / KPIs, above the long result tables. */
export default function AnalysisWorkspaceClient({ viewer }: { viewer?: ReactNode } = {}) {
  const { lang } = useUiLang();
  const t = useMemo(() => makeAnalysisT(lang), [lang]);
  const { projects, selectedProjectId, setSelectedProjectId, selectedProject, loading, error } = useProjectScope();
  const [payload, setPayload] = useState<unknown>(null);
  const [inputs, setInputs] = useState<Record<string, unknown> | null>(null);
  const [lastRun, setLastRun] = useState<LastRun | null>(null);
  const [run, setRun] = useState<RunState>({ kind: "idle" });

  const sync = useCallback(() => {
    if (!selectedProjectId) {
      setPayload(null);
      setInputs(null);
      setLastRun(null);
      return;
    }
    const saved = loadFrame3dInputs(selectedProjectId);
    if (!saved) void hydrateFrame3dFromServer(selectedProjectId);
    setInputs(saved);
    setPayload(loadFrame3dPayload(selectedProjectId));
    setLastRun(loadLastRun(selectedProjectId));
  }, [selectedProjectId]);

  useEffect(() => {
    setRun({ kind: "idle" });
    sync();
    window.addEventListener(FRAME3D_EVENT, sync);
    window.addEventListener(PROJECT_EVENT, sync);
    return () => {
      window.removeEventListener(FRAME3D_EVENT, sync);
      window.removeEventListener(PROJECT_EVENT, sync);
    };
  }, [sync]);

  const view = useMemo(() => summarizeAnalysis(payload), [payload]);
  // The model the solver would run: the saved model inputs, or the inputs recorded in the last payload.
  const modelInputs = inputs ?? view?.inputs ?? null;
  const missing = missingModelInputs(modelInputs);
  const noProject = !selectedProjectId;
  const noModel = !noProject && !modelInputs;
  const disabledReasons: string[] = [];
  if (noProject) disabledReasons.push(t("Select a project first."));
  else if (noModel) disabledReasons.push(t("No model saved for this project yet. Build one on the Model page or describe it in the chat."));
  else if (missing.length) disabledReasons.push(`${t("Required inputs are missing:")} ${missing.map((k) => t(inputLabel(k))).join("، ")}`);
  const running = run.kind === "running";
  const disabled = running || disabledReasons.length > 0;

  async function analyze() {
    if (disabled || !modelInputs) return;
    setRun({ kind: "running" });
    try {
      const fresh = await runFrame3d(modelInputs);
      saveFrame3dInputs(selectedProjectId, modelInputs);
      saveFrame3dPayload(selectedProjectId, fresh);
      const stamp = { at: new Date().toISOString(), ok: true };
      saveLastRun(selectedProjectId, stamp);
      setPayload(fresh);
      setLastRun(stamp);
      const fv = summarizeAnalysis(fresh);
      if (fv && !fv.completed) setRun({ kind: "error", message: fv.message || t("Analysis failed") });
      else setRun({ kind: "ok" });
    } catch (err) {
      setRun({ kind: "error", message: err instanceof Error ? err.message : String(err) });
    }
  }

  const hasResults = !!view && view.completed;
  const nStoreys = modelInputs ? Number(modelInputs.storeys) : NaN;
  const nBaysX = modelInputs ? Number(modelInputs.bays_x) : NaN;
  const nBaysY = modelInputs ? Number(modelInputs.bays_y) : NaN;
  const modelLine = Number.isFinite(nStoreys) && Number.isFinite(nBaysX) && Number.isFinite(nBaysY)
    ? `${t("Current model")}: ${nStoreys} ${t("storeys")} · ${nBaysX}×${nBaysY} ${t("bays")}`
    : null;
  const dateText = lastRun
    ? new Date(lastRun.at).toLocaleString(lang === "fa" ? "fa-IR" : "en-US", { dateStyle: "medium", timeStyle: "short" })
    : t("Date not recorded");

  const button = (
    <button
      type="button"
      className="button an-analyze"
      onClick={() => void analyze()}
      disabled={disabled}
      aria-busy={running}
      aria-describedby={disabledReasons.length ? "an-why" : undefined}
      data-testid="analyze-button"
    >
      {running ? t("Analyzing…") : t("Analyze")}
    </button>
  );

  const messages = (
    <>
      {disabledReasons.length > 0 ? (
        <div className="an-why" id="an-why" role="note" data-testid="analyze-disabled-reason">
          <strong>{t("Analysis is disabled")}</strong>
          <ul>{disabledReasons.map((r) => <li key={r}>{r}</li>)}</ul>
          {!noProject ? <Link href="/workspace/model">{t("Model page")}</Link> : null}
        </div>
      ) : null}
      {run.kind === "ok" ? <div className="an-msg ok" role="status" data-testid="analyze-success">{t("Analysis succeeded. The results below are updated.")}</div> : null}
      {run.kind === "error" ? (
        <div className="an-msg err" role="alert" data-testid="analyze-error">
          <strong>{t("Analysis run failed")}</strong>: {run.message}
          {hasResults ? <> {t("The previous results are still shown below.")}</> : null}
        </div>
      ) : null}
    </>
  );

  return (
    <div className="an-page" dir={lang === "fa" ? "rtl" : "ltr"} data-testid="analysis-page">
      <header className="an-head">
        <div>
          <p className="eyebrow">{t("Analysis")}</p>
          <h2>{t("Project analysis")}</h2>
          <p className="subtitle">{t("Results of the built-in 3D frame solver for the current model of this project.")}</p>
        </div>
        <label className="an-project">
          <span>{t("Project")}</span>
          <select className="input project-select" value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} disabled={loading || projects.length === 0}>
            {projects.length === 0 ? <option value="">—</option> : null}
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
      </header>

      {error ? <div className="an-msg err" role="alert">{error}</div> : null}

      {hasResults && view ? (
        <section className="an-run" data-testid="analysis-banner">
          <div className="an-run-main">
            <div className="an-run-info">
              <div>
                <span className="an-chip pass">✓ {t("Analysis completed")}</span>
              </div>
              <div className="an-run-chips">
                <span><b>{t("Last analysis")}</b>{dateText}</span>
                {view.seismicCode ? <span><b>{t("Seismic code")}</b><bdi>{view.seismicCode.replace(/_/g, " ")}</bdi></span> : null}
                <span><b>{t("Units")}</b><bdi>{unitSystemLabel()}</bdi></span>
              </div>
              {modelLine || selectedProject ? <div className="an-run-model">{selectedProject?.name}{modelLine ? ` — ${modelLine}` : ""}</div> : null}
              {view.code ? <div className="an-run-model" dir="auto"><b>{t("Design code")}:</b> <bdi>{view.code}</bdi></div> : null}
            </div>
            {button}
          </div>
          {messages}
        </section>
      ) : (
        <section className="an-run empty" data-testid="analysis-empty">
          <div className="an-run-main">
            <div>
              <h3>{view && !view.completed ? t("Model saved, not analysed yet") : t("No analysis results yet")}</h3>
              <p className="muted">{t("Press Analyze to run the solver on the current model. Results will appear here.")}</p>
              {modelLine ? <p className="an-run-model">{modelLine}</p> : null}
            </div>
            {button}
          </div>
          {messages}
        </section>
      )}

      {hasResults && view ? <AnalysisKpis view={view} t={t} /> : null}
      {viewer}
      {hasResults && view ? <AnalysisSections view={view} t={t} /> : null}
    </div>
  );
}
