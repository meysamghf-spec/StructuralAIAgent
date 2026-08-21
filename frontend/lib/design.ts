import { apiFetch } from "./api";

export type DesignResultResponse = {
  id: string | null;
  project_id: string;
  design_type: string;
  status: string;
  capability_status: string;
  message: string;
  code_edition: string | null;
  pem_snapshot_id?: string | null;
  pem_version?: number | null;
  analysis_run_id?: string | null;
  outputs: Record<string, unknown>;
  model_summary: Record<string, unknown>;
  validation_summary: Record<string, unknown>;
  created_at?: string | null;
};

export type DesignRunSummary = {
  id: string;
  project_id: string;
  pem_snapshot_id: string;
  pem_version: number;
  analysis_run_id: string | null;
  design_type: string;
  status: string;
  capability_status: string;
  message: string;
  code_edition: string | null;
  model_summary: Record<string, unknown>;
  validation_summary: Record<string, unknown>;
  outputs: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
};

export type DesignReadinessResponse = {
  project_id: string;
  pem_version: number;
  pem_snapshot_id: string;
  ready_for_design: boolean;
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
};

export type DesignRunListResponse = {
  project_id: string;
  runs: DesignRunSummary[];
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

export async function runDesign(
  projectId: string,
  designType: string,
  options?: { pemVersion?: number; analysisRunId?: string },
): Promise<DesignResultResponse> {
  return apiFetch<DesignResultResponse>("/api/v1/engineering/design/run", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      design_type: designType,
      parameters: {},
      pem_version: options?.pemVersion ?? null,
      analysis_run_id: options?.analysisRunId ?? null,
    }),
  });
}

export async function getDesignReadiness(
  projectId: string,
  pemVersion?: number,
): Promise<DesignReadinessResponse> {
  const query = pemVersion ? `?pem_version=${pemVersion}` : "";
  return apiFetch<DesignReadinessResponse>(
    `/api/v1/engineering/design/${projectId}/readiness${query}`,
  );
}

export async function listDesignRuns(projectId: string): Promise<DesignRunListResponse> {
  return apiFetch<DesignRunListResponse>(`/api/v1/engineering/design/${projectId}/runs`);
}

export async function listAvailableAnalysisRuns(projectId: string): Promise<{
  project_id: string;
  analysis_runs: AvailableAnalysisRun[];
}> {
  return apiFetch(`/api/v1/engineering/design/${projectId}/analysis-runs`);
}
