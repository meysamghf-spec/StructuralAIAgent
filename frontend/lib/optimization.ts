import { apiFetch } from "./api";

export type OptimizationResultResponse = {
  id: string | null;
  project_id: string;
  optimization_type: string;
  objective: string;
  status: string;
  capability_status: string;
  message: string;
  code_edition: string | null;
  pem_snapshot_id?: string | null;
  pem_version?: number | null;
  analysis_run_id?: string | null;
  design_run_id?: string | null;
  constraints: Record<string, unknown>;
  outputs: Record<string, unknown>;
  model_summary: Record<string, unknown>;
  validation_summary: Record<string, unknown>;
  created_at?: string | null;
};

export type OptimizationRunSummary = {
  id: string;
  project_id: string;
  pem_snapshot_id: string;
  pem_version: number;
  analysis_run_id: string | null;
  design_run_id: string | null;
  optimization_type: string;
  objective: string;
  status: string;
  capability_status: string;
  message: string;
  code_edition: string | null;
  constraints: Record<string, unknown>;
  model_summary: Record<string, unknown>;
  validation_summary: Record<string, unknown>;
  outputs: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
};

export type OptimizationReadinessResponse = {
  project_id: string;
  pem_version: number;
  pem_snapshot_id: string;
  ready_for_optimization: boolean;
  readiness_status: string;
  summary: string;
  code_edition: string | null;
  code_configuration_valid: boolean;
  model_summary: Record<string, unknown>;
  validation_status: string;
  findings: Array<{ code: string; message: string; status: string }>;
  missing_requirements: string[];
  available_analysis_runs: number;
  usable_analysis_runs: number;
  available_design_runs: number;
  usable_design_runs: number;
  checklist?: import("./optimization-checklist").OptimizationChecklist;
  /** Chat-built frame or imported model found outside the PEM (the full optimizer runs on it). */
  detected_model?: {
    source: "frame" | "model";
    member_count: number;
    label?: { en: string; fa: string };
  } | null;
};

export type OptimizationRunListResponse = {
  project_id: string;
  runs: OptimizationRunSummary[];
};

export type AvailableAnalysisRun = {
  id: string;
  analysis_type: string;
  status: string;
  capability_status: string;
  pem_version: number;
  engineering_results_available: boolean;
  created_at: string;
  message: string;
};

export type AvailableDesignRun = {
  id: string;
  design_type: string;
  status: string;
  capability_status: string;
  pem_version: number;
  analysis_run_id: string | null;
  engineering_design_results_available: boolean;
  created_at: string;
  message: string;
};

export async function runOptimization(
  projectId: string,
  optimizationType: string,
  objective: string,
  options?: {
    pemVersion?: number;
    analysisRunId?: string;
    designRunId?: string;
    constraints?: Record<string, unknown>;
    parameters?: Record<string, unknown>;
  },
): Promise<OptimizationResultResponse> {
  return apiFetch<OptimizationResultResponse>("/api/v1/engineering/optimization/run", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      optimization_type: optimizationType,
      objective,
      constraints: options?.constraints ?? {},
      parameters: options?.parameters ?? {},
      pem_version: options?.pemVersion ?? null,
      analysis_run_id: options?.analysisRunId ?? null,
      design_run_id: options?.designRunId ?? null,
    }),
  });
}

export async function getOptimizationReadiness(
  projectId: string,
  pemVersion?: number,
): Promise<OptimizationReadinessResponse> {
  const query = pemVersion ? `?pem_version=${pemVersion}` : "";
  return apiFetch<OptimizationReadinessResponse>(
    `/api/v1/engineering/optimization/${projectId}/readiness${query}`,
  );
}

export async function listOptimizationRuns(
  projectId: string,
): Promise<OptimizationRunListResponse> {
  return apiFetch<OptimizationRunListResponse>(
    `/api/v1/engineering/optimization/${projectId}/runs`,
  );
}

export async function listOptimizationAnalysisRuns(projectId: string): Promise<{
  project_id: string;
  analysis_runs: AvailableAnalysisRun[];
}> {
  return apiFetch(`/api/v1/engineering/optimization/${projectId}/analysis-runs`);
}

export async function listOptimizationDesignRuns(projectId: string): Promise<{
  project_id: string;
  design_runs: AvailableDesignRun[];
}> {
  return apiFetch(`/api/v1/engineering/optimization/${projectId}/design-runs`);
}
