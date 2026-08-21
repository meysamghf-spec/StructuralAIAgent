import { apiFetch } from "./api";

export type ModelSummaryResponse = {
  project_id: string;
  pem_version: number;
  snapshot_id: string;
  project_name: string;
  grid_count: number;
  level_count: number;
  material_count: number;
  section_count: number;
  member_count: number;
  support_count: number;
  load_case_count: number;
  load_combination_count: number;
  analysis_status: string;
  validation_status: string;
};

export type ModelValidationResponse = {
  project_id: string;
  overall_status: string;
  summary: string;
  findings: Array<{
    code: string;
    message: string;
    status: string;
    category: string;
  }>;
};

export type StructuralModelResponse = {
  project_id: string;
  pem_version: number;
  snapshot_id: string;
  structural_model: Record<string, unknown>;
  code_configuration: Record<string, unknown>;
  unit_configuration: Record<string, unknown>;
};

export type PemVersionListResponse = {
  project_id: string;
  versions: number[];
};

export type RevisionSummary = {
  revision_number: number;
  change_type: string;
  summary: string;
  created_by: string | null;
  created_at: string;
};

export type RevisionListResponse = {
  revisions: RevisionSummary[];
};

export async function getModelSummary(projectId: string): Promise<ModelSummaryResponse> {
  return apiFetch<ModelSummaryResponse>(`/api/v1/projects/${projectId}/model/summary`);
}

export async function getCurrentModel(projectId: string): Promise<StructuralModelResponse> {
  return apiFetch<StructuralModelResponse>(`/api/v1/projects/${projectId}/model`);
}

export async function validateModel(projectId: string): Promise<ModelValidationResponse> {
  return apiFetch<ModelValidationResponse>(`/api/v1/projects/${projectId}/model/validate`, {
    method: "POST",
  });
}

export async function listPemVersions(projectId: string): Promise<PemVersionListResponse> {
  return apiFetch<PemVersionListResponse>(`/api/v1/projects/${projectId}/pem/versions`);
}

export async function listRevisions(projectId: string): Promise<RevisionListResponse> {
  return apiFetch<RevisionListResponse>(`/api/v1/projects/${projectId}/revisions`);
}
