"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { getTraceabilityLineage, type TraceabilityLinkSummary } from "@/lib/api";
import { listAnalysisRuns, getAnalysisReadiness, type AnalysisRunSummary } from "@/lib/analysis";
import { listDesignRuns, getDesignReadiness, type DesignRunSummary } from "@/lib/design";
import {
  getEngineeringResultValidation,
  listEngineeringResults,
  type EngineeringResultSet,
  type EngineeringResultValidation,
} from "@/lib/engineering-results";
import { getOptimizationReadiness, listOptimizationRuns, type OptimizationRunSummary } from "@/lib/optimization";
import {
  formatMissingRequirements,
  formatValidationFindings,
  getNextStepMessage,
  getResultReadinessMessage,
  getResultSourceLabel,
  getExtractionStatusLabel,
  summarizeExtractionCategories,
  getResultTypeLabels,
  getSolverDisplayName,
  getValidationStatusLabel,
  summarizeResultLineage,
} from "@/lib/results-workspace";
import { formatWorkspaceDate } from "@/lib/workspace";
import Link from "next/link";
import { StructuralSetSection } from "@/components/autocad/StructuralSetSection";
import { FrameDownloads } from "@/components/frame3d/FrameDownloads";
import { ReportPanel } from "@/components/frame3d/ReportPanel";
import { useCallback, useEffect, useState } from "react";

function badgeClass(status: string): string {
  if (status === "VALIDATED") return "status-pass";
  if (status === "INVALID") return "status-error";
  if (status === "PARTIALLY_VALIDATED" || status === "INCOMPLETE") return "status-warning";
  return "status-review";
}

function projectLink(path: string, projectId: string): string {
  return `${path}?project=${projectId}`;
}

export default function ResultsWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [results, setResults] = useState<EngineeringResultSet[]>([]);
  const [runs, setRuns] = useState<AnalysisRunSummary[]>([]);
  const [designRuns, setDesignRuns] = useState<DesignRunSummary[]>([]);
  const [optimizationRuns, setOptimizationRuns] = useState<OptimizationRunSummary[]>([]);
  const [analysisReady, setAnalysisReady] = useState<string>("");
  const [designReady, setDesignReady] = useState<string>("");
  const [optimizationReady, setOptimizationReady] = useState<string>("");
  const [selectedResult, setSelectedResult] = useState<EngineeringResultSet | null>(null);
  const [inlineView, setInlineView] = useState<"design" | "reports" | "cad" | null>(null);
  const [validationDetails, setValidationDetails] = useState<EngineeringResultValidation | null>(
    null,
  );
  const [lineageLinks, setLineageLinks] = useState<TraceabilityLinkSummary[]>([]);

  const loadResultsContext = useCallback(async () => {
    if (!selectedProjectId) {
      setResults([]);
      setRuns([]);
      setDesignRuns([]);
      setOptimizationRuns([]);
      setSelectedResult(null);
      setValidationDetails(null);
      setLineageLinks([]);
      return;
    }
    const [resultData, runData, designData, optimizationData, analysisData, designReadyData, optimizationReadyData] =
      await Promise.all([
        listEngineeringResults(selectedProjectId),
        listAnalysisRuns(selectedProjectId),
        listDesignRuns(selectedProjectId),
        listOptimizationRuns(selectedProjectId),
        getAnalysisReadiness(selectedProjectId),
        getDesignReadiness(selectedProjectId),
        getOptimizationReadiness(selectedProjectId),
      ]);
    setResults(resultData);
    setRuns(runData.runs);
    setDesignRuns(designData.runs);
    setOptimizationRuns(optimizationData.runs);
    setAnalysisReady(analysisData.summary);
    setDesignReady(designReadyData.summary);
    setOptimizationReady(optimizationReadyData.summary);
    setSelectedResult(resultData[0] ?? null);
  }, [selectedProjectId]);

  useEffect(() => {
    async function load() {
      try {
        await loadResultsContext();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load results workspace");
      }
    }
    void load();
  }, [loadResultsContext, setError]);

  useEffect(() => {
    async function loadSelectedDetails() {
      if (!selectedProjectId || !selectedResult) {
        setValidationDetails(null);
        setLineageLinks([]);
        return;
      }
      try {
        const [validation, lineage] = await Promise.all([
          getEngineeringResultValidation(selectedProjectId, selectedResult.id),
          getTraceabilityLineage(selectedProjectId, "engineering_result", selectedResult.id),
        ]);
        setValidationDetails(validation);
        setLineageLinks(lineage.links);
      } catch (err) {
        setValidationDetails(null);
        setLineageLinks([]);
        setError(err instanceof Error ? err.message : "Failed to load result details");
      }
    }
    void loadSelectedDetails();
  }, [selectedProjectId, selectedResult, setError]);

  const linkedRun = selectedResult?.analysis_run_id
    ? runs.find((run) => run.id === selectedResult.analysis_run_id)
    : null;

  const linkedDesignRuns = selectedResult?.analysis_run_id
    ? designRuns.filter((run) => run.analysis_run_id === selectedResult.analysis_run_id)
    : [];

  const linkedOptimizationRuns = selectedResult?.analysis_run_id
    ? optimizationRuns.filter((run) => run.analysis_run_id === selectedResult.analysis_run_id)
    : [];

  const validationFindings = formatValidationFindings(validationDetails?.validation_summary ?? {});
  const missingRequirements = formatMissingRequirements(validationDetails?.validation_summary ?? {});
  const lineageSummary = summarizeResultLineage(lineageLinks);
  const extractionSummary =
    (selectedResult?.metadata?.extraction_summary as Record<string, unknown> | undefined) ??
    undefined;
  const extractionStatus =
    typeof selectedResult?.metadata?.extraction_status === "string"
      ? selectedResult.metadata.extraction_status
      : undefined;
  const extractionCategories = summarizeExtractionCategories(extractionSummary);

  return (
    <div className="workspace-page">
      <header className="page-header">
        <p className="eyebrow">Results</p>
        <h2>Results</h2>
        <p className="subtitle">Review analysis, design, and optimization results.</p>
      </header>
      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
        description="Review validated solver results, provenance, and downstream readiness."
      />

      {error ? <p className="workspace-error">{error}</p> : null}

      <section className="workspace-card-grid">
        <article className="workspace-card">
          <h2>Analysis readiness</h2>
          <p>{analysisReady || "Select a project to review analysis readiness."}</p>
        </article>
        <article className="workspace-card">
          <h2>Design readiness</h2>
          <p>{designReady || "Design readiness will appear after the model is configured."}</p>
        </article>
        <article className="workspace-card">
          <h2>Optimization readiness</h2>
          <p>{optimizationReady || "Optimization readiness depends on validated upstream results."}</p>
        </article>
      </section>

      <section className="workspace-card">
        <h2>Result history</h2>
        {results.length === 0 ? (
          <div>
            <p>No validated result sets yet.</p>
            <p className="workspace-help">
              Run analysis from the Analysis workspace after connecting a solver on this computer.
            </p>
            {selectedProjectId ? (
              <p className="workspace-help">
                <Link href={projectLink("/workspace/analysis", selectedProjectId)}>Open Analysis workspace</Link>
              </p>
            ) : null}
          </div>
        ) : (
          <ul className="workspace-list">
            {results.map((item) => (
              <li key={item.id} className="workspace-list-item">
                <button type="button" className="workspace-link-button" onClick={() => setSelectedResult(item)}>
                  <strong>{getSolverDisplayName(item.software, item.software_version)}</strong>
                  <span className={badgeClass(item.validation_status)}>
                    {getValidationStatusLabel(item.validation_status)}
                  </span>
                  <span>{getResultReadinessMessage(item.validation_status, item.engineering_results_available)}</span>
                  <span className="workspace-meta">{formatWorkspaceDate(item.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selectedResult && selectedProjectId ? (
        <>
          <section className="workspace-card">
            <h2>Selected result</h2>
            <p>{getResultReadinessMessage(selectedResult.validation_status, selectedResult.engineering_results_available)}</p>
            <p className="workspace-meta">
              Solver: {getSolverDisplayName(selectedResult.software, selectedResult.software_version)}
            </p>
            <p className="workspace-meta">Result source: {getResultSourceLabel(selectedResult)}</p>
            {extractionStatus ? (
              <p className="workspace-meta">
                CSI extraction: {getExtractionStatusLabel(extractionStatus)}
              </p>
            ) : null}
            <p className="workspace-meta">Analysis type: {selectedResult.analysis_type}</p>
            <p className="workspace-meta">Engineering model version: v{selectedResult.pem_version}</p>
            {linkedRun ? (
              <p className="workspace-meta">
                Linked analysis run: {linkedRun.analysis_type} ({linkedRun.status})
              </p>
            ) : (
              <p className="workspace-meta">No linked analysis run recorded for this result set.</p>
            )}
            {selectedResult.result_types.length > 0 ? (
              <p>Result types: {getResultTypeLabels(selectedResult.result_types).join(", ")}</p>
            ) : null}
            <p className="workspace-help">
              {getNextStepMessage(selectedResult.validation_status, selectedResult.engineering_results_available)}
            </p>
            <div className="workspace-card-grid">
              {selectedResult.engineering_results_available ? (
                <>
                  <button type="button" className="workspace-link-button" aria-expanded={inlineView === "design"} onClick={() => setInlineView(inlineView === "design" ? null : "design")}>
                    {inlineView === "design" ? "Hide design" : "Show design"}
                  </button>
                  <Link
                    className="workspace-link-button"
                    href={projectLink("/workspace/optimization", selectedProjectId)}
                  >
                    Open Optimization
                  </Link>
                </>
              ) : null}
              <button type="button" className="workspace-link-button" aria-expanded={inlineView === "reports"} onClick={() => setInlineView(inlineView === "reports" ? null : "reports")}>
                {inlineView === "reports" ? "Hide report" : "Show report"}
              </button>
              <button type="button" className="workspace-link-button" aria-expanded={inlineView === "cad"} onClick={() => setInlineView(inlineView === "cad" ? null : "cad")}>
                {inlineView === "cad" ? "Hide drawings" : "Show drawings"}
              </button>
              <Link
                className="workspace-link-button"
                href={projectLink("/workspace/traceability", selectedProjectId)}
              >
                View Traceability
              </Link>
            </div>
            {inlineView ? (
              <div className="inline-panel" data-testid={`results-inline-${inlineView}`}>
                {inlineView === "design" ? <FrameDownloads groups={["design", "foundation"]} title="Design results" /> : null}
                {inlineView === "reports" ? <ReportPanel /> : null}
                {inlineView === "cad" ? <StructuralSetSection /> : null}
              </div>
            ) : null}
          </section>

          <section className="workspace-card">
            <h2>Validation details</h2>
            {validationDetails ? (
              <>
                <p>
                  Status:{" "}
                  <span className={badgeClass(validationDetails.validation_status)}>
                    {getValidationStatusLabel(validationDetails.validation_status)}
                  </span>
                </p>
                {validationFindings.length > 0 ? (
                  <ul className="workspace-list">
                    {validationFindings.map((finding) => (
                      <li key={finding}>{finding}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="workspace-help">No validation issues were recorded for this result set.</p>
                )}
                {missingRequirements.length > 0 ? (
                  <>
                    <h3>Still needed</h3>
                    <ul className="workspace-list">
                      {missingRequirements.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </>
            ) : (
              <p className="workspace-help">Loading validation details…</p>
            )}
          </section>

          {extractionCategories.length > 0 ? (
            <section className="workspace-card">
              <h2>CSI extraction summary</h2>
              <ul className="workspace-list">
                {extractionCategories.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="workspace-card">
            <h2>Downstream usage</h2>
            {linkedDesignRuns.length === 0 && linkedOptimizationRuns.length === 0 ? (
              <p className="workspace-help">
                No design or optimization runs have consumed this analysis run yet.
              </p>
            ) : null}
            {linkedDesignRuns.length > 0 ? (
              <>
                <h3>Design runs</h3>
                <ul className="workspace-list">
                  {linkedDesignRuns.map((run) => (
                    <li key={run.id}>
                      {run.design_type} — {run.status} ({formatWorkspaceDate(run.created_at)})
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {linkedOptimizationRuns.length > 0 ? (
              <>
                <h3>Optimization runs</h3>
                <ul className="workspace-list">
                  {linkedOptimizationRuns.map((run) => (
                    <li key={run.id}>
                      {run.optimization_type} — {run.status} ({formatWorkspaceDate(run.created_at)})
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </section>

          <section className="workspace-card">
            <h2>Traceability chain</h2>
            {lineageSummary.length > 0 ? (
              <ul className="workspace-list">
                {lineageSummary.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="workspace-help">
                Traceability links will appear once this result is connected to analysis, solver export, or
                downstream engineering steps.
              </p>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
