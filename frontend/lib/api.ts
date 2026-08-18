const DEFAULT_API_BASE = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_BASE;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Request failed (${response.status})`;
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export type ProjectSummary = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};

export type ProjectListResponse = {
  projects: ProjectSummary[];
};

export type CreateProjectResponse = {
  project: ProjectSummary;
  pem_version: number;
};

export type HealthResponse = {
  status: string;
};

export type EngineeringAgentType =
  | "STRUCTURAL_MODELING_AGENT"
  | "LOAD_ASSESSMENT_AGENT"
  | "ANALYSIS_AGENT"
  | "CONCRETE_DESIGN_AGENT"
  | "STEEL_DESIGN_AGENT"
  | "SEISMIC_AGENT"
  | "VALIDATION_AGENT"
  | "CAD_AGENT"
  | "REPORTING_AGENT"
  | "DOCUMENT_INTERPRETATION_AGENT"
  | "PROMPT_GENERATION_AGENT";

export type AgentDefinitionSummary = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  agent_type: EngineeringAgentType | null;
  status: string;
  current_version: number | null;
  configuration: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AgentListResponse = {
  agents: AgentDefinitionSummary[];
};

export type AgentExecutionStatus =
  | "CREATED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "WAITING_APPROVAL"
  | "CANCELLED";

export type AgentExecutionSummary = {
  id: string;
  project_id: string;
  agent_definition_id: string;
  agent_version: number;
  execution_status: AgentExecutionStatus;
  approval_request_id: string | null;
  validation_status: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentExecutionListResponse = {
  executions: AgentExecutionSummary[];
};

export async function listAgents(): Promise<AgentListResponse> {
  return apiFetch<AgentListResponse>("/api/v1/agents");
}

export async function listAgentExecutions(projectId: string): Promise<AgentExecutionListResponse> {
  return apiFetch<AgentExecutionListResponse>(`/api/v1/agent-executions?project_id=${projectId}`);
}
