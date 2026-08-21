import { apiFetch } from "./api";

export type EngineeringResultSet = {
  id: string;
  project_id: string;
  analysis_run_id: string | null;
  integration_execution_id: string | null;
  pem_snapshot_id: string;
  pem_version: number;
  software: string;
  software_version: string;
  analysis_type: string;
  validation_status: string;
  engineering_results_available: boolean;
  result_types: string[];
  validation_summary: Record<string, unknown>;
  provenance: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  created_at: string;
};

export type EngineeringResultValidation = {
  result_set_id: string;
  validation_status: string;
  engineering_results_available: boolean;
  result_types: string[];
  validation_summary: Record<string, unknown>;
};

export type EngineeringResultListResponse = {
  project_id: string;
  results: EngineeringResultSet[];
};

export async function listEngineeringResults(
  projectId: string,
  analysisRunId?: string,
): Promise<EngineeringResultSet[]> {
  const query = analysisRunId ? `?analysis_run_id=${analysisRunId}` : "";
  const response = await apiFetch<EngineeringResultListResponse>(
    `/api/v1/engineering/results/${projectId}${query}`,
  );
  return response.results;
}

export async function getEngineeringResult(
  projectId: string,
  resultSetId: string,
): Promise<EngineeringResultSet> {
  return apiFetch<EngineeringResultSet>(
    `/api/v1/engineering/results/${projectId}/${resultSetId}`,
  );
}

export async function getEngineeringResultValidation(
  projectId: string,
  resultSetId: string,
): Promise<EngineeringResultValidation> {
  return apiFetch<EngineeringResultValidation>(
    `/api/v1/engineering/results/${projectId}/${resultSetId}/validation`,
  );
}
