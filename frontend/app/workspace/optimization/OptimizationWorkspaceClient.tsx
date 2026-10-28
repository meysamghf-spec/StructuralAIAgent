"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { FrameDownloads } from "@/components/frame3d/FrameDownloads";
import { OptimizationChecklist } from "@/components/optimization/OptimizationChecklist";
import { isChecklist } from "@/lib/optimization-checklist";
import { FrameOptimizerPanel } from "@/components/optimization/FrameOptimizerPanel";
import {
  formatMemberOptimizationResults,
  formatOptimizationInventory,
  formatOptimizationMode,
  formatSharedSectionGroups,
  getOptimizationCapabilityLabel,
  getOptimizationStatusLabel,
} from "@/lib/optimization-workspace";
import {
  getOptimizationReadiness,
  listOptimizationAnalysisRuns,
  listOptimizationDesignRuns,
  listOptimizationRuns,
  runOptimization,
  type AvailableAnalysisRun,
  type AvailableDesignRun,
  type OptimizationReadinessResponse,
  type OptimizationResultResponse,
  type OptimizationRunSummary,
} from "@/lib/optimization";
import { listPemVersions } from "@/lib/model";
import { formatWorkspaceDate, getValidationStatusLabel } from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

const OPTIMIZATION_OPTIONS = [
  { value: "WEIGHT", label: "Minimize structural weight" },
  { value: "MATERIAL_EFFICIENCY", label: "Improve material efficiency" },
  { value: "ESTIMATED_COST", label: "Reduce estimated cost" },
  { value: "MEMBER_SIZE", label: "Optimize member sizes" },
  { value: "CONSTRUCTABILITY", label: "Improve constructability" },
  { value: "CODE_COMPLIANCE", label: "Enhance code compliance margin" },
  { value: "PERFORMANCE", label: "Improve structural performance" },
];

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "pass" || normalized === "success") return "status-pass";
  if (normalized === "fail" || normalized === "model_not_ready") return "status-error";
  if (
    normalized === "warning" ||
    normalized === "requires_solver" ||
    normalized === "requires_analysis" ||
    normalized === "requires_design"
  ) {
    return "status-warning";
  }
  return "status-review";
}

export default function OptimizationWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [optimizationType, setOptimizationType] = useState("WEIGHT");
  const [objective, setObjective] = useState("Minimize structural weight");
  const [selectedVersion, setSelectedVersion] = useState<number | "current">("current");
  const [selectedAnalysisRunId, setSelectedAnalysisRunId] = useState<string>("");
  const [selectedDesignRunId, setSelectedDesignRunId] = useState<string>("");
  const [versions, setVersions] = useState<number[]>([]);
  const [readiness, setReadiness] = useState<OptimizationReadinessResponse | null>(null);
  const [analysisRuns, setAnalysisRuns] = useState<AvailableAnalysisRun[]>([]);
  const [designRuns, setDesignRuns] = useState<AvailableDesignRun[]>([]);
  const [runs, setRuns] = useState<OptimizationRunSummary[]>([]);
  const [result, setResult] = useState<OptimizationResultResponse | null>(null);
  const [optimizationMode, setOptimizationMode] = useState<"INDEPENDENT" | "SHARED_SECTION">(
    "INDEPENDENT",
  );
  const [memberSelection, setMemberSelection] = useState("");
  const [busy, setBusy] = useState(false);

  const loadOptimizationContext = useCallback(async () => {
    if (!selectedProjectId) {
      setReadiness(null);
      setAnalysisRuns([]);
      setDesignRuns([]);
      setRuns([]);
      setVersions([]);
      setResult(null);
      return;
    }
    setError(null);
    const versionData = await listPemVersions(selectedProjectId);
    setVersions(versionData.versions);
    const pemVersion = selectedVersion === "current" ? undefined : selectedVersion;
    const [readinessData, analysisData, designData, runData] = await Promise.all([
      getOptimizationReadiness(selectedProjectId, pemVersion),
      listOptimizationAnalysisRuns(selectedProjectId),
      listOptimizationDesignRuns(selectedProjectId),
      listOptimizationRuns(selectedProjectId),
    ]);
    setReadiness(readinessData);
    setAnalysisRuns(analysisData.analysis_runs);
    setDesignRuns(designData.design_runs);
    setRuns(runData.runs);
  }, [selectedProjectId, selectedVersion, setError]);

  useEffect(() => {
    async function load() {
      try {
        await loadOptimizationContext();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load optimization workspace");
      }
    }
    void load();
  }, [loadOptimizationContext, setError]);

  function handleOptimizationTypeChange(value: string) {
    setOptimizationType(value);
    const option = OPTIMIZATION_OPTIONS.find((item) => item.value === value);
    if (option) {
      setObjective(option.label);
    }
  }

  async function handleRun() {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    try {
      const pemVersion = selectedVersion === "current" ? undefined : selectedVersion;
      const memberIds = memberSelection
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const runResult = await runOptimization(
        selectedProjectId,
        optimizationType,
        objective,
        {
          pemVersion,
          analysisRunId: selectedAnalysisRunId || undefined,
          designRunId: selectedDesignRunId || undefined,
          parameters: {
            optimization_mode: optimizationMode,
            ...(memberIds.length > 0 ? { member_ids: memberIds } : {}),
          },
        },
      );
      setResult(runResult);
      await loadOptimizationContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization run failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Optimization</p>
        <h2 className="page-dup-title">Optimization</h2>
        <p className="subtitle">Set optimization goals from your model and recorded runs.</p>
      </header>

      <FrameOptimizerPanel />
      <FrameDownloads groups={["analysis", "design", "figures"]} title="Current frame model downloads" collapsed />

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
          <h3>Optimization readiness</h3>
          {readiness ? (
            <>
              <p className={`status-pill ${statusClass(readiness.readiness_status)}`}>
                {getOptimizationStatusLabel(readiness.readiness_status)}
              </p>
              <p className="muted">{readiness.summary}</p>
              {isChecklist(readiness.checklist) ? (
                <OptimizationChecklist checklist={readiness.checklist} projectId={selectedProjectId} />
              ) : null}
              <details className="meta-summary">
                <summary>Details</summary>
              <ul className="feature-list">
                {formatOptimizationInventory(readiness.model_summary).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              </details>
              <p className="muted">Governing code: {readiness.code_edition ?? "—"}</p>
              <p className="muted">
                Validation: {getValidationStatusLabel(readiness.validation_status)}
              </p>
              <p className="muted">
                Usable analysis runs: {readiness.usable_analysis_runs} /{" "}
                {readiness.available_analysis_runs}
              </p>
              <p className="muted">
                Usable design runs: {readiness.usable_design_runs} /{" "}
                {readiness.available_design_runs}
              </p>
            </>
          ) : (
            <p className="muted">Select a project to review optimization readiness.</p>
          )}
        </article>

        <article className="card">
          <h3>Upstream engineering runs</h3>
          {analysisRuns.length === 0 && designRuns.length === 0 ? (
            <p className="muted">No analysis or design runs are linked to this project yet.</p>
          ) : (
            <>
              {analysisRuns.length > 0 ? (
                <>
                  <h4>Analysis</h4>
                  <ul className="feature-list">
                    {analysisRuns.slice(0, 4).map((run) => (
                      <li key={run.id}>
                        {run.analysis_type} · v{run.pem_version} ·{" "}
                        {run.engineering_results_available
                          ? "Engineering outputs available"
                          : "No engineering outputs yet"}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
              {designRuns.length > 0 ? (
                <>
                  <h4>Design</h4>
                  <ul className="feature-list">
                    {designRuns.slice(0, 4).map((run) => (
                      <li key={run.id}>
                        {run.design_type} · v{run.pem_version} ·{" "}
                        {run.engineering_design_results_available
                          ? "Design outputs available"
                          : "No design outputs yet"}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </>
          )}
        </article>
      </div>

      <section className="card">
        <h3>Start optimization</h3>
        <div className="form-row">
          <select
            className="input"
            value={optimizationType}
            onChange={(event) => handleOptimizationTypeChange(event.target.value)}
          >
            {OPTIMIZATION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            className="input"
            type="text"
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            placeholder="Optimization objective"
          />
        </div>
        <div className="form-row">
          <select
            className="input"
            value={optimizationMode}
            onChange={(event) =>
              setOptimizationMode(event.target.value as "INDEPENDENT" | "SHARED_SECTION")
            }
          >
            <option value="INDEPENDENT">Independent section per member</option>
            <option value="SHARED_SECTION">One shared section for selected members</option>
          </select>
          <input
            className="input"
            type="text"
            value={memberSelection}
            onChange={(event) => setMemberSelection(event.target.value)}
            placeholder="Member IDs (optional, comma-separated)"
          />
        </div>
        <div className="form-row">
          <select
            className="input"
            value={selectedAnalysisRunId}
            onChange={(event) => setSelectedAnalysisRunId(event.target.value)}
          >
            <option value="">Auto-select latest analysis run</option>
            {analysisRuns.map((run) => (
              <option key={run.id} value={run.id}>
                Analysis: {run.analysis_type} · v{run.pem_version}
              </option>
            ))}
          </select>
          <select
            className="input"
            value={selectedDesignRunId}
            onChange={(event) => setSelectedDesignRunId(event.target.value)}
          >
            <option value="">Auto-select latest design run</option>
            {designRuns.map((run) => (
              <option key={run.id} value={run.id}>
                Design: {run.design_type} · v{run.pem_version}
              </option>
            ))}
          </select>
          <button
            className="button"
            type="button"
            disabled={!selectedProjectId || busy}
            onClick={() => void handleRun()}
          >
            {busy ? "Running…" : "Start optimization"}
          </button>
        </div>
        <p className="muted">{getOptimizationCapabilityLabel("REQUIRES_SOLVER", "fa")}</p>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {result ? (
        <section className="card">
          <h3>Latest optimization result</h3>
          <p className={`status-pill ${statusClass(result.status)}`}>
            {getOptimizationStatusLabel(result.status)}
          </p>
          <p className="muted">{getOptimizationCapabilityLabel(result.capability_status)}</p>
          <p className="muted">{getOptimizationCapabilityLabel(result.capability_status, "fa")}</p>
          <div className="execution-result">
            <p className="result-text">{result.message}</p>
          </div>
          {result.outputs?.engineering_optimization_results_available === false ? (
            <p className="muted">No structural optimization was performed in this run.</p>
          ) : null}
          {formatMemberOptimizationResults(result.outputs ?? {}).length > 0 ? (
            <>
              <p className="muted">{formatOptimizationMode(String(result.outputs?.optimization_mode))}</p>
              <ul className="feature-list">
                {formatMemberOptimizationResults(result.outputs ?? {}).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
          {formatSharedSectionGroups(result.outputs ?? {}).map((item) => (
            <p key={item} className="muted">
              {item}
            </p>
          ))}
        </section>
      ) : null}

      <section className="card">
        <h3>Optimization history</h3>
        {runs.length === 0 ? (
          <p className="muted">No optimization runs yet. Choose an objective above and start a run.</p>
        ) : (
          <ul className="timeline-list">
            {runs.map((run) => (
              <li key={run.id}>
                <strong>
                  {run.objective} · {getOptimizationStatusLabel(run.status)}
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
