import { apiFetch } from "./api";

export type SoftwareCapability = {
  software: "ETABS" | "SAP2000" | "SAFE";
  expected_version: string;
  availability: string;
  detected_version: string | null;
  install_path: string | null;
  message: string;
  metadata: Record<string, unknown>;
};

export type IntegrationExecution = {
  id: string;
  project_id: string;
  software: string;
  operation: string;
  status: string;
  pem_snapshot_id: string | null;
  pem_version: number | null;
  analysis_run_id: string | null;
  message: string;
  outputs: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
};

export async function listSolverCapabilities(): Promise<SoftwareCapability[]> {
  return apiFetch<SoftwareCapability[]>("/api/v1/integrations/capabilities");
}

export async function listIntegrationExecutions(
  projectId: string,
  software?: string,
): Promise<IntegrationExecution[]> {
  const query = software ? `?software=${software}` : "";
  return apiFetch<IntegrationExecution[]>(`/api/v1/integrations/${projectId}/executions${query}`);
}

export async function connectSolver(projectId: string, software: string): Promise<IntegrationExecution> {
  return apiFetch<IntegrationExecution>(`/api/v1/integrations/${projectId}/connect/${software}`, {
    method: "POST",
  });
}

export async function disconnectSolver(
  projectId: string,
  software: string,
): Promise<IntegrationExecution> {
  return apiFetch<IntegrationExecution>(`/api/v1/integrations/${projectId}/disconnect/${software}`, {
    method: "POST",
  });
}

export async function exportModelToSolver(
  projectId: string,
  software: string,
  pemVersion?: number,
): Promise<IntegrationExecution> {
  const query = pemVersion ? `?pem_version=${pemVersion}` : "";
  return apiFetch<IntegrationExecution>(
    `/api/v1/integrations/${projectId}/export/${software}${query}`,
    { method: "POST" },
  );
}
