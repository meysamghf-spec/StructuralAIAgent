"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  formatAnalysisInventory,
  getAnalysisCapabilityLabel,
  getAnalysisStatusLabel,
} from "@/lib/analysis-workspace";
import {
  getAnalysisReadiness,
  getLoadCombinationSummary,
  listAnalysisRuns,
  runAnalysis,
  type AnalysisReadinessResponse,
  type AnalysisResultResponse,
  type AnalysisRunSummary,
  type LoadCombinationSummaryResponse,
} from "@/lib/analysis";
import { listPemVersions } from "@/lib/model";
import { formatWorkspaceDate, getValidationStatusLabel } from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

const ANALYSIS_OPTIONS = [
  { value: "STATIC", label: "Static analysis" },
  { value: "MODAL", label: "Modal analysis" },
  { value: "DRIFT", label: "Drift review" },
  { value: "LATERAL_DRIFT", label: "Lateral drift review" },
];

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "success") return "status-pass";
  if (normalized === "failed" || normalized === "model_not_ready") return "status-error";
  if (normalized === "warning" || normalized === "requires_solver") return "status-warning";
  return "status-review";
}

export default function AnalysisWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [analysisType, setAnalysisType] = useState("STATIC");
  const [selectedVersion, setSelectedVersion] = useState<number | "current">("current");
  const [versions, setVersions] = useState<number[]>([]);
  const [readiness, setReadiness] = useState<AnalysisReadinessResponse | null>(null);
  const [loadSummary, setLoadSummary] = useState<LoadCombinationSummaryResponse | null>(null);
  const [runs, setRuns] = useState<AnalysisRunSummary[]>([]);
  const [result, setResult] = useState<AnalysisResultResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const loadAnalysisContext = useCallback(async () => {
    if (!selectedProjectId) {
      setReadiness(null);
      setLoadSummary(null);
      setRuns([]);
      setVersions([]);
      setResult(null);
      return;
    }
    setError(null);
    const versionData = await listPemVersions(selectedProjectId);
    setVersions(versionData.versions);
    const pemVersion = selectedVersion === "current" ? undefined : selectedVersion;
    const [readinessData, loadData, runData] = await Promise.all([
      getAnalysisReadiness(selectedProjectId, pemVersion),
      getLoadCombinationSummary(selectedProjectId),
      listAnalysisRuns(selectedProjectId),
    ]);
    setReadiness(readinessData);
    setLoadSummary(loadData);
    setRuns(runData.runs);
  }, [selectedProjectId, selectedVersion, setError]);

  useEffect(() => {
    async function load() {
      try {
        await loadAnalysisContext();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load analysis workspace");
      }
    }
    void load();
  }, [loadAnalysisContext, setError]);

  async function handleRun() {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    try {
      const pemVersion = selectedVersion === "current" ? undefined : selectedVersion;
      const runResult = await runAnalysis(selectedProjectId, analysisType, { pemVersion });
      setResult(runResult);
      await loadAnalysisContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Analysis</p>
        <h2>Structural Analysis</h2>
        <p className="subtitle">Prepare analysis inputs and track analysis runs.</p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      {selectedProjectId ? (
        <section className="card">
          <h3>Model revision</h3>
          <div className="form-row">
            <select
              className="input"
              value={selectedVersion === "current" ? "current" : String(selectedVersion)}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedVersion(value === "current" ? "current" : Number(value));
              }}
            >
              <option value="current">Current model</option>
              {versions.map((version) => (
                <option key={version} value={version}>
                  Version {version}
                </option>
              ))}
            </select>
          </div>
        </section>
      ) : null}

      <div className="grid cards-2">
        <article className="card">
          <h3>Model readiness</h3>
          {readiness ? (
            <>
              <p className={`status-pill ${statusClass(readiness.readiness_status)}`}>
                {getAnalysisStatusLabel(readiness.readiness_status)}
              </p>
              <p className="muted">{readiness.summary}</p>
              <details className="meta-summary">
                <summary>Details</summary>
              <ul className="feature-list">
                {formatAnalysisInventory(readiness.model_summary).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {readiness.missing_requirements.length > 0 ? (
                <ul className="feature-list">
                  {readiness.missing_requirements.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
              <p className="muted">
                Validation: {getValidationStatusLabel(readiness.validation_status)}
              </p>
              </details>
            </>
          ) : (
            <p className="muted">Select a project to review model readiness.</p>
          )}
        </article>

        <article className="card">
          <h3>Load combinations</h3>
          {loadSummary ? (
            <>
              <p className="metric">{loadSummary.load_combination_count} combinations</p>
              <p className="muted">{loadSummary.load_case_count} load cases</p>
              <p className="muted">
                Analysis model: {loadSummary.analysis_model_status.replaceAll("_", " ").toLowerCase()}
              </p>
              {loadSummary.load_combinations.length === 0 ? (
                <p className="muted">No load combinations defined in the current model.</p>
              ) : (
                <ul className="feature-list">
                  {loadSummary.load_combinations.slice(0, 6).map((combo) => (
                    <li key={String(combo.id)}>{String(combo.name ?? combo.id)}</li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="muted">Load combination summary will appear here.</p>
          )}
        </article>
      </div>

      <section className="card">
        <h3>Run analysis</h3>
        <div className="form-row">
          <select
            className="input"
            value={analysisType}
            onChange={(event) => setAnalysisType(event.target.value)}
          >
            {ANALYSIS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            className="button"
            type="button"
            disabled={!selectedProjectId || busy}
            onClick={() => void handleRun()}
          >
            {busy ? "Running…" : "Run analysis"}
          </button>
        </div>
        <p className="muted">
          The platform prepares deterministic model inputs and records the run. Forces, displacements,
          and modal results are not generated until a solver adapter is connected.
        </p>
        <p className="muted">
          This page does not read a prompt. To analyse a described 3D frame (e.g. “Analyze and design per Mabhas 9 a
          3-storey RC frame, 2x2 bays of 5 m …”), send it in the <a href="/">Chat</a>: it runs the built-in 3D frame solver
          and shows the result card.
        </p>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {result ? (
        <section className="card">
          <h3>Latest run result</h3>
          <p className={`status-pill ${statusClass(result.status)}`}>
            {getAnalysisStatusLabel(result.status)}
          </p>
          <p className="muted">{getAnalysisCapabilityLabel(result.capability_status)}</p>
          <div className="execution-result">
            <p className="result-text">{result.message}</p>
          </div>
          {result.outputs?.engineering_results_available === false ? (
            <p className="muted">No engineering analysis results were generated in this run.</p>
          ) : null}
        </section>
      ) : null}

      <section className="card">
        <h3>Run history</h3>
        {runs.length === 0 ? (
          <p className="muted">No analysis runs yet. Check readiness above, then start a run.</p>
        ) : (
          <ul className="timeline-list">
            {runs.map((run) => (
              <li key={run.id}>
                <strong>
                  {run.analysis_type} · {getAnalysisStatusLabel(run.status)}
                </strong>
                <span>{run.message}</span>
                <span className="muted">
                  Model v{run.pem_version} · {formatWorkspaceDate(run.created_at)}
                  {run.created_by ? ` · ${run.created_by}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
