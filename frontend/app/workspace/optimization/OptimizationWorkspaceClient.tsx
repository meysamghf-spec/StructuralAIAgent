"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { FrameDownloads } from "@/components/frame3d/FrameDownloads";
import { OptimizationChecklist } from "@/components/optimization/OptimizationChecklist";
import { isChecklist } from "@/lib/optimization-checklist";
import { FullOptimizationSection } from "@/components/optimization/FullOptimizationSection";
import { FrameOptimizerPanel } from "@/components/optimization/FrameOptimizerPanel";
import {
  NO_MODEL_MESSAGE_FA,
  NO_MODEL_STEPS_FA,
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
  type AvailableAnalysisRun,
  type AvailableDesignRun,
  type OptimizationReadinessResponse,
  type OptimizationResultResponse,
  type OptimizationRunSummary,
} from "@/lib/optimization";
import { listPemVersions } from "@/lib/model";
import {
  barsLabel,
  cancelJob,
  fmtNum,
  getJob,
  isActive,
  OptApiError,
  savingsPct,
  startJob,
  type OptJob,
} from "@/lib/optimization-full";
import { formatWorkspaceDate, getValidationStatusLabel } from "@/lib/workspace";
import { useCallback, useEffect, useRef, useState } from "react";

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
  const [fullJob, setFullJob] = useState<OptJob | null>(null);
  const [noModel, setNoModel] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (pollTimer.current) clearTimeout(pollTimer.current); }, []);

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

  function pollFullJob(id: string) {
    pollTimer.current = setTimeout(async () => {
      try {
        const j = await getJob(id);
        setFullJob(j);
        if (isActive(j)) pollFullJob(id);
        else void loadOptimizationContext().catch(() => undefined);
      } catch (err) {
        setError(err instanceof OptApiError ? err.fa : err instanceof Error ? err.message : "Optimization run failed");
      }
    }, 1500);
  }

  /** Runs the real full optimizer (/api/v1/optimization-full) on the project's model: imported model if present,
   *  otherwise the latest chat / Model-page 3D frame. Results show in "Latest optimization result". */
  async function handleRun() {
    if (!selectedProjectId) return;
    if (pollTimer.current) clearTimeout(pollTimer.current);
    setBusy(true);
    setError(null);
    setNoModel(false);
    setResult(null);
    setFullJob(null);
    const source = readiness?.detected_model?.source ?? "frame";
    const options = {
      time_budget_s: 120,
      storey_band: optimizationMode === "SHARED_SECTION" ? 50 : 1,
    };
    try {
      let job: OptJob;
      try {
        job = await startJob({ source, project_id: selectedProjectId, options });
      } catch (err) {
        // No imported model → fall back to the chat frame (and vice versa) before reporting "no model".
        if (err instanceof OptApiError && err.status === 409 && source === "model") {
          job = await startJob({ source: "frame", project_id: selectedProjectId, options });
        } else {
          throw err;
        }
      }
      setFullJob(job);
      pollFullJob(job.id);
    } catch (err) {
      if (err instanceof OptApiError && (err.status === 409 || err.status === 422) && !/blocking|مسدود/.test(err.message + err.fa)) {
        setNoModel(true);
      } else {
        setError(err instanceof OptApiError ? err.fa : err instanceof Error ? err.message : "Optimization run failed");
      }
    } finally {
      setBusy(false);
    }
  }

  const fullResult = fullJob?.result ?? null;
  const fullPct = Math.round((fullJob?.progress?.fraction ?? 0) * 100);
  const fullSave = fullResult ? savingsPct(fullResult) : null;

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Optimization</p>
        <h2 className="page-dup-title">Optimization</h2>
        <p className="subtitle">Set optimization goals from your model and recorded runs.</p>
      </header>

      <FrameOptimizerPanel />
      <FullOptimizationSection />
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
            disabled={!selectedProjectId || busy || isActive(fullJob)}
            onClick={() => void handleRun()}
          >
            {busy || isActive(fullJob) ? "Running…" : "Start optimization"}
          </button>
          {isActive(fullJob) ? (
            <button
              className="button secondary"
              type="button"
              onClick={() => fullJob && void cancelJob(fullJob.id).catch(() => undefined)}
            >
              توقف
            </button>
          ) : null}
        </div>
        <p className="muted" dir="rtl" lang="fa" style={{ textAlign: "right" }}>
          {getOptimizationCapabilityLabel("REQUIRES_SOLVER", "fa")}
          {readiness?.detected_model
            ? ` مدل شناسایی‌شده: ${readiness.detected_model.label?.fa ?? ""} (${fmtNum(readiness.detected_model.member_count)} عضو).`
            : ""}
        </p>
        {noModel ? (
          <div className="alert" role="alert" dir="rtl" lang="fa" style={{ textAlign: "right" }}>
            <p><strong>{NO_MODEL_MESSAGE_FA}</strong></p>
            <ol>
              {NO_MODEL_STEPS_FA.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
        ) : null}
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {fullJob && !result ? (
        <section className="card">
          <h3>Latest optimization result</h3>
          <div dir="rtl" lang="fa" style={{ textAlign: "right" }} aria-live="polite">
            <progress value={fullPct} max={100} style={{ width: "100%" }} />
            <p className="muted">
              وضعیت:{" "}
              {({ queued: "در صف", running: "در حال اجرا", done: "پایان یافت", cancelled: "متوقف شد", error: "خطا" } as const)[fullJob.status]}
              {" — "}{fmtNum(fullPct)}٪ — ارزیابی‌ها: {fmtNum(fullJob.progress?.evals)}
              {fullJob.progress?.best_cost ? <> — بهترین هزینه: {fmtNum(fullJob.progress.best_cost)} تومان</> : null}
            </p>
            {fullJob.error ? <p role="alert" style={{ color: "#b91c1c" }}>{fullJob.error}</p> : null}
            {fullResult ? (
              <>
                <p className={`status-pill ${fullResult.feasible ? "status-pass" : "status-warning"}`}>
                  {fullResult.feasible ? "طرح قابل‌قبول (همه کنترل‌ها برقرار)" : "طرحی که همه کنترل‌ها را برقرار کند هنوز یافت نشد"}
                </p>
                <p>
                  هزینه: {fmtNum(fullResult.cost)} {fullResult.currency}
                  {fullSave != null ? ` (${fmtNum(fullSave, 1)}٪ کاهش نسبت به شروع)` : ""} — دریفت/مجاز: {fmtNum(fullResult.drift_ratio, 2)}
                  {" — "}{fmtNum(fullResult.evaluations)} تحلیل در {fmtNum(fullResult.elapsed_s, 1)} ثانیه
                </p>
                <div style={{ overflowX: "auto" }}>
                  <table className="data-table" style={{ minWidth: 520, width: "100%" }}>
                    <thead>
                      <tr><th>گروه</th><th>اعضا</th><th>مقطع</th><th>میلگرد</th><th>D/C</th></tr>
                    </thead>
                    <tbody>
                      {fullResult.groups.map((g) => (
                        <tr key={g.group}>
                          <td>{g.label}</td><td>{fmtNum(g.members)}</td><td dir="ltr">{g.section}</td>
                          <td dir="ltr">{barsLabel(g)}</td>
                          <td style={{ color: g.DC > 1 ? "#b91c1c" : undefined }}>{fmtNum(g.DC, 2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {[...fullResult.assumptions, ...(fullResult.assumed_inputs ?? [])].length > 0 ? (
                  <details className="meta-summary">
                    <summary>فرض‌ها</summary>
                    <ul>{[...fullResult.assumptions, ...(fullResult.assumed_inputs ?? [])].map((a) => <li key={a}>{a}</li>)}</ul>
                  </details>
                ) : null}
              </>
            ) : null}
          </div>
        </section>
      ) : null}

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
