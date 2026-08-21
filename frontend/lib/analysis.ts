import { apiFetch } from "./api";

export type AnalysisResultResponse = {
  id: string | null;
  project_id: string;
  analysis_type: string;
  status: string;
  capability_status: string;
  message: string;
  pem_snapshot_id?: string | null;
  pem_version?: number | null;
  model_version_id?: string | null;
  outputs: Record<string, unknown>;
  model_summary: Record<string, unknown>;
  validation_summary: Record<string, unknown>;
  created_at?: string | null;
};

export type AnalysisRunSummary = {
  id: string;
  project_id: string;
  pem_snapshot_id: string;
  pem_version: number;
  analysis_type: string;
  status: string;
  capability_status: string;
  message: string;
  model_summary: Record<string, unknown>;
  validation_summary: Record<string, unknown>;
  outputs: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
};

export type AnalysisReadinessResponse = {
  project_id: string;
  pem_version: number;
  pem_snapshot_id: string;
  ready_for_solver: boolean;
  readiness_status: string;
  summary: string;
  model_summary: Record<string, unknown>;
  validation_status: string;
  findings: Array<{ code: string; message: string; status: string }>;
  missing_requirements: string[];
};

export type AnalysisRunListResponse = {
  project_id: string;
  runs: AnalysisRunSummary[];
};

export type LoadCombinationSummaryResponse = {
  project_id: string;
  pem_snapshot_id: string;
  pem_version: number;
  load_combination_count: number;
  load_case_count: number;
  load_combinations: Array<Record<string, unknown>>;
  load_cases: Array<Record<string, unknown>>;
  analysis_model_status: string;
};

export async function runAnalysis(
  projectId: string,
  analysisType: string,
  options?: { pemVersion?: number; solver?: string },
): Promise<AnalysisResultResponse> {
  return apiFetch<AnalysisResultResponse>("/api/v1/engineering/analysis/run", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      analysis_type: analysisType,
      parameters: options?.solver ? { solver: options.solver } : {},
      pem_version: options?.pemVersion ?? null,
    }),
  });
}

export async function getAnalysisReadiness(
  projectId: string,
  pemVersion?: number,
): Promise<AnalysisReadinessResponse> {
  const query = pemVersion ? `?pem_version=${pemVersion}` : "";
  return apiFetch<AnalysisReadinessResponse>(
    `/api/v1/engineering/analysis/${projectId}/readiness${query}`,
  );
}

export async function listAnalysisRuns(projectId: string): Promise<AnalysisRunListResponse> {
  return apiFetch<AnalysisRunListResponse>(`/api/v1/engineering/analysis/${projectId}/runs`);
}

export async function getAnalysisRun(
  projectId: string,
  runId: string,
): Promise<AnalysisRunSummary> {
  return apiFetch<AnalysisRunSummary>(`/api/v1/engineering/analysis/${projectId}/runs/${runId}`);
}

export async function getLoadCombinationSummary(
  projectId: string,
): Promise<LoadCombinationSummaryResponse> {
  return apiFetch<LoadCombinationSummaryResponse>(
    `/api/v1/engineering/analysis/${projectId}/load-combinations`,
  );
}
