"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  formatDesignInventory,
  getDesignCapabilityLabel,
  getDesignStatusLabel,
} from "@/lib/design-workspace";
import {
  getDesignReadiness,
  listAvailableAnalysisRuns,
  listDesignRuns,
  runDesign,
  type AvailableAnalysisRun,
  type DesignReadinessResponse,
  type DesignResultResponse,
  type DesignRunSummary,
} from "@/lib/design";
import { listPemVersions } from "@/lib/model";
import { formatWorkspaceDate, getValidationStatusLabel } from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

const DESIGN_OPTIONS = [
  { value: "CONCRETE_BEAM", label: "Concrete beam design" },
  { value: "STEEL_BEAM", label: "Steel beam design" },
  { value: "CONCRETE_COLUMN", label: "Concrete column design" },
  { value: "STEEL_COLUMN", label: "Steel column design" },
];

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "pass" || normalized === "success") return "status-pass";
  if (normalized === "fail" || normalized === "model_not_ready") return "status-error";
  if (
    normalized === "warning" ||
    normalized === "requires_solver" ||
    normalized === "requires_analysis"
  ) {
    return "status-warning";
  }
  return "status-review";
}

export default function DesignLegacyClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [designType, setDesignType] = useState("CONCRETE_BEAM");
  const [selectedVersion, setSelectedVersion] = useState<number | "current">("current");
  const [selectedAnalysisRunId, setSelectedAnalysisRunId] = useState<string>("");
  const [versions, setVersions] = useState<number[]>([]);
  const [readiness, setReadiness] = useState<DesignReadinessResponse | null>(null);
  const [analysisRuns, setAnalysisRuns] = useState<AvailableAnalysisRun[]>([]);
  const [runs, setRuns] = useState<DesignRunSummary[]>([]);
  const [result, setResult] = useState<DesignResultResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const loadDesignContext = useCallback(async () => {
    if (!selectedProjectId) {
      setReadiness(null);
      setAnalysisRuns([]);
      setRuns([]);
      setVersions([]);
      setResult(null);
      return;
    }
    setError(null);
    const versionData = await listPemVersions(selectedProjectId);
    setVersions(versionData.versions);
    const pemVersion = selectedVersion === "current" ? undefined : selectedVersion;
    const [readinessData, analysisData, runData] = await Promise.all([
      getDesignReadiness(selectedProjectId, pemVersion),
      listAvailableAnalysisRuns(selectedProjectId),
      listDesignRuns(selectedProjectId),
    ]);
    setReadiness(readinessData);
    setAnalysisRuns(analysisData.analysis_runs);
    setRuns(runData.runs);
  }, [selectedProjectId, selectedVersion, setError]);

  useEffect(() => {
    async function load() {
      try {
        await loadDesignContext();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load design workspace");
      }
    }
    void load();
  }, [loadDesignContext, setError]);

  async function handleRun() {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    try {
      const pemVersion = selectedVersion === "current" ? undefined : selectedVersion;
      const runResult = await runDesign(selectedProjectId, designType, {
        pemVersion,
        analysisRunId: selectedAnalysisRunId || undefined,
      });
      setResult(runResult);
      await loadDesignContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Design check failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Design</p>
        <h2 className="page-dup-title">Design</h2>
        <p className="subtitle">Run code-based design checks from your model.</p>
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
          <h3>Design readiness</h3>
          {readiness ? (
            <>
              <p className={`status-pill ${statusClass(readiness.readiness_status)}`}>
                {getDesignStatusLabel(readiness.readiness_status)}
              </p>
              <p className="muted">{readiness.summary}</p>
              <details className="meta-summary">
                <summary>Details</summary>
              <ul className="feature-list">
                {formatDesignInventory(readiness.model_summary).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              </details>
              <p className="muted">Governing steel code: {readiness.code_edition ?? "—"}</p>
              <p className="muted">
                Validation: {getValidationStatusLabel(readiness.validation_status)}
              </p>
              <p className="muted">
                Usable analysis runs: {readiness.usable_analysis_runs} /{" "}
                {readiness.available_analysis_runs}
              </p>
            </>
          ) : (
            <p className="muted">Select a project to review design readiness.</p>
          )}
        </article>

        <article className="card">
          <h3>Available analysis runs</h3>
          {analysisRuns.length === 0 ? (
            <p className="muted">No analysis runs yet. Run one on the Analysis page first.</p>
          ) : (
            <ul className="feature-list">
              {analysisRuns.slice(0, 6).map((run) => (
                <li key={run.id}>
                  {run.analysis_type} · v{run.pem_version} ·{" "}
                  {run.engineering_results_available
                    ? "Engineering outputs available"
                    : "No engineering outputs yet"}
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>

      <section className="card">
        <h3>Run design check</h3>
        <div className="form-row">
          <select
            className="input"
            value={designType}
            onChange={(event) => setDesignType(event.target.value)}
          >
            {DESIGN_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="input"
            value={selectedAnalysisRunId}
            onChange={(event) => setSelectedAnalysisRunId(event.target.value)}
          >
            <option value="">Auto-select latest analysis run</option>
            {analysisRuns.map((run) => (
              <option key={run.id} value={run.id}>
                {run.analysis_type} · v{run.pem_version}
              </option>
            ))}
          </select>
          <button
            className="button"
            type="button"
            disabled={!selectedProjectId || busy}
            onClick={() => void handleRun()}
          >
            {busy ? "Running…" : "Run design check"}
          </button>
        </div>
        <p className="muted">
          {getDesignCapabilityLabel("REQUIRES_SOLVER")}
        </p>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {result ? (
        <section className="card">
          <h3>Latest design result</h3>
          <p className={`status-pill ${statusClass(result.status)}`}>
            {getDesignStatusLabel(result.status)}
          </p>
          <p className="muted">{getDesignCapabilityLabel(result.capability_status)}</p>
          <p className="muted">{getDesignCapabilityLabel(result.capability_status)}</p>
          <div className="execution-result">
            <p className="result-text">{result.message}</p>
          </div>
          {result.outputs?.engineering_design_results_available === false ? (
            <p className="muted">No code-based design calculations were performed in this run.</p>
          ) : null}
        </section>
      ) : null}

      <section className="card">
        <h3>Design run history</h3>
        {runs.length === 0 ? (
          <p className="muted">No design runs yet. Link an analysis run, then start a design check.</p>
        ) : (
          <ul className="timeline-list">
            {runs.map((run) => (
              <li key={run.id}>
                <strong>
                  {run.design_type} · {getDesignStatusLabel(run.status)}
                </strong>
                <span>{run.message}</span>
                <span className="muted">
                  Model v{run.pem_version}
                  {run.code_edition ? ` · ${run.code_edition}` : ""} ·{" "}
                  {formatWorkspaceDate(run.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
