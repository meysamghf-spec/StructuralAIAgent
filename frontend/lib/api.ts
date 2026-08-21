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

export type PromptGenerationResult = {
  selected_agent_type: EngineeringAgentType;
  generated_prompt: string;
  user_intent: string;
  engineering_objectives: string[];
  required_inputs: string[];
  missing_information: string[];
  deterministic_services: string[];
  execution_plan: Array<{
    step_number: number;
    title: string;
    description: string;
    capability: string;
    capability_kind: "agent" | "deterministic_service";
  }>;
  preserved_constraints: string[];
};

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
  user_view: AgentExecutionUserView;
  prompt_generation?: PromptGenerationResult | null;
  traceability_metadata?: {
    report_id?: string;
    [key: string]: unknown;
  };
};

export type AgentExecutionUserView = {
  progress: "starting" | "in_progress" | "awaiting_approval" | "completed" | "rejected" | "failed" | "cancelled";
  requires_approval: boolean;
  approval_request_id: string | null;
  final_result: string | null;
  summary: string | null;
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

export type CreateAgentExecutionRequest = {
  project_id: string;
  user_request: string;
  agent_type?: EngineeringAgentType;
  requires_approval?: boolean;
};

export async function createAgentExecution(
  body: CreateAgentExecutionRequest,
): Promise<AgentExecutionSummary> {
  return apiFetch<AgentExecutionSummary>("/api/v1/agent-executions", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "X-Actor-Id": "workspace-user" },
  });
}

export async function planAgentExecution(
  projectId: string,
  userRequest: string,
): Promise<PromptGenerationResult> {
  return apiFetch<PromptGenerationResult>("/api/v1/agent-executions/plan", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, user_request: userRequest }),
  });
}

export async function approveAgentRequest(
  projectId: string,
  approvalRequestId: string,
  approver: string,
  decisionNote?: string,
): Promise<void> {
  await apiFetch(`/api/v1/approvals/${approvalRequestId}/approve?project_id=${projectId}`, {
    method: "POST",
    body: JSON.stringify({ approver, decision_note: decisionNote ?? null }),
  });
}

export async function rejectAgentRequest(
  projectId: string,
  approvalRequestId: string,
  approver: string,
  rejectionReason: string,
): Promise<void> {
  await apiFetch(`/api/v1/approvals/${approvalRequestId}/reject?project_id=${projectId}`, {
    method: "POST",
    body: JSON.stringify({ approver, rejection_reason: rejectionReason }),
  });
}

export type ApprovalSummary = {
  id: string;
  project_id: string;
  requester: string;
  target_type: string;
  target_action: string;
  target_object_type: string | null;
  target_object_id: string | null;
  summary: string;
  status: string;
  approver: string | null;
  rejection_reason: string | null;
  requested_at: string;
  resolved_at: string | null;
};

export type ApprovalListResponse = {
  requests: ApprovalSummary[];
};

export async function listApprovals(
  projectId: string,
  status?: string,
): Promise<ApprovalListResponse> {
  const query = status
    ? `/api/v1/approvals?project_id=${projectId}&status=${status}`
    : `/api/v1/approvals?project_id=${projectId}`;
  return apiFetch<ApprovalListResponse>(query);
}

export async function listPendingApprovals(projectId: string): Promise<ApprovalListResponse> {
  return apiFetch<ApprovalListResponse>(`/api/v1/approvals/pending?project_id=${projectId}`);
}

export type ReportSummary = {
  id: string;
  project_id: string;
  report_type: string;
  title: string;
  status: string;
  current_version: number;
  created_at: string;
  updated_at: string;
};

export type ReportListResponse = {
  reports: ReportSummary[];
};

export type ReportVersionSummary = {
  id: string;
  report_id: string;
  version: number;
  status: string;
  content: Record<string, unknown>;
  generated_at: string;
};

export async function listReports(projectId: string): Promise<ReportListResponse> {
  return apiFetch<ReportListResponse>(`/api/v1/reports?project_id=${projectId}`);
}

export async function createReport(
  projectId: string,
  reportType: string,
  title?: string,
): Promise<ReportSummary> {
  return apiFetch<ReportSummary>("/api/v1/reports", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      report_type: reportType,
      title,
      created_by: "workspace-user",
    }),
  });
}

export async function generateReportVersion(
  projectId: string,
  reportId: string,
  reportType: string,
): Promise<ReportVersionSummary> {
  return apiFetch<ReportVersionSummary>(
    `/api/v1/reports/${reportId}/generate?project_id=${projectId}`,
    {
      method: "POST",
      body: JSON.stringify({
        report_type: reportType,
        output_format: "STRUCTURED",
        requested_by: "workspace-user",
      }),
    },
  );
}

export type ProjectFileSummary = {
  id: string;
  filename: string;
  file_type: string;
  parsing_status: string;
  extraction_status: string;
  upload_time: string;
  created_at: string;
};

export type ProjectFileListResponse = {
  project_id: string;
  files: ProjectFileSummary[];
};

export async function listProjectFiles(projectId: string): Promise<ProjectFileListResponse> {
  return apiFetch<ProjectFileListResponse>(`/api/v1/projects/${projectId}/files`);
}

export async function uploadProjectFile(projectId: string, file: File): Promise<ProjectFileSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${getApiBaseUrl()}/api/v1/projects/${projectId}/files`, {
    method: "POST",
    body: formData,
    headers: { "X-Actor-Id": "workspace-user" },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Upload failed (${response.status})`;
    throw new Error(message);
  }
  return response.json() as Promise<ProjectFileSummary>;
}

export type MemorySummary = {
  id: string;
  memory_type: string;
  content: string;
  source_type: string | null;
  created_at: string;
  created_by: string | null;
};

export type MemoryListResponse = {
  memories: MemorySummary[];
};

export type MemoryContextResponse = {
  project_id: string;
  memories: MemorySummary[];
  total_count: number;
  counts_by_type: Record<string, number>;
};

export async function listProjectMemory(projectId: string): Promise<MemoryListResponse> {
  return apiFetch<MemoryListResponse>(`/api/v1/projects/${projectId}/memory`);
}

export async function getProjectMemoryContext(projectId: string): Promise<MemoryContextResponse> {
  return apiFetch<MemoryContextResponse>(`/api/v1/projects/${projectId}/memory/context`);
}

export type TraceabilityLinkSummary = {
  id: string;
  source_type: string;
  target_type: string;
  relationship_type: string;
  created_at: string;
};

export type TraceabilityGraphResponse = {
  project_id: string;
  links: TraceabilityLinkSummary[];
};

export async function getTraceabilityGraph(projectId: string): Promise<TraceabilityGraphResponse> {
  return apiFetch<TraceabilityGraphResponse>(`/api/v1/traceability/graph?project_id=${projectId}`);
}

export type TraceabilityChainResponse = {
  project_id: string;
  origin: { object_type: string; object_id: string };
  links: TraceabilityLinkSummary[];
  nodes: Array<{ object_type: string; object_id: string }>;
};

export async function getTraceabilityLineage(
  projectId: string,
  objectType: string,
  objectId: string,
): Promise<TraceabilityChainResponse> {
  const params = new URLSearchParams({
    project_id: projectId,
    object_type: objectType,
    object_id: objectId,
  });
  return apiFetch<TraceabilityChainResponse>(`/api/v1/traceability/target?${params.toString()}`);
}

export type ProjectContextResponse = {
  project_id: string;
  project_name: string;
  pem_version: number | null;
  code_configuration: {
    jurisdiction: string;
    governing_building_code: string;
    loading_standard: string;
    concrete_standard: string;
    steel_standard: string;
  } | null;
  unit_configuration: {
    system: string;
    length_unit: string;
    force_unit: string;
    stress_unit: string;
  } | null;
  memory_total_count: number;
  files: Array<{ id: string; filename: string; extraction_status: string }>;
};

export async function getProjectContext(projectId: string): Promise<ProjectContextResponse> {
  return apiFetch<ProjectContextResponse>(`/api/v1/projects/${projectId}/context`);
}

export type ValidationReportResponse = {
  project_id: string;
  overall_status: string;
  summary: string;
  findings: Array<{ code: string; message: string; status: string; category: string }>;
};

export async function runProjectValidation(projectId: string): Promise<ValidationReportResponse> {
  return apiFetch<ValidationReportResponse>(`/api/v1/projects/${projectId}/validate`, {
    method: "POST",
  });
}

export type AnalysisResultResponse = {
  project_id: string;
  analysis_type: string;
  status: string;
  message: string;
  outputs: Record<string, unknown>;
};

export async function runAnalysis(
  projectId: string,
  analysisType: string,
): Promise<AnalysisResultResponse> {
  return apiFetch<AnalysisResultResponse>("/api/v1/engineering/analysis/run", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, analysis_type: analysisType, parameters: {} }),
  });
}

export type DesignResultResponse = {
  project_id: string;
  design_type: string;
  status: string;
  message: string;
  outputs: Record<string, unknown>;
};

export async function runDesign(
  projectId: string,
  designType: string,
): Promise<DesignResultResponse> {
  return apiFetch<DesignResultResponse>("/api/v1/engineering/design/run", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, design_type: designType, parameters: {} }),
  });
}

export async function completeAiPrompt(prompt: string): Promise<{ content: string; provider: string }> {
  const response = await apiFetch<{ content: string; provider: string; model: string }>(
    "/api/v1/ai/complete",
    {
      method: "POST",
      body: JSON.stringify({
        model: "stub-default",
        messages: [
          { role: "system", content: "You are a structural engineering assistant." },
          { role: "user", content: prompt },
        ],
      }),
    },
  );
  return { content: response.content, provider: response.provider };
}

export type AgentCapabilitySummary = {
  id: string;
  key: string;
  name: string;
  description: string | null;
};

export type AgentBuilderValidationIssue = {
  code: string;
  message: string;
  severity: string;
};

export type AgentBuilderValidation = {
  valid: boolean;
  issues: AgentBuilderValidationIssue[];
};

export type AgentBuilderDetail = {
  agent: AgentDefinitionSummary & { project_id?: string | null };
  version: {
    id: string;
    version: number;
    instructions: string | null;
    configuration_metadata: Record<string, unknown>;
    status: string;
    capabilities: AgentCapabilitySummary[];
  };
  validation: AgentBuilderValidation;
};

export type AgentVersionTestSummary = {
  id: string;
  agent_version: number;
  project_id: string;
  validation_status: string | null;
  result: Record<string, unknown>;
  created_at: string;
};

export type AgentBuilderPublicationSummary = {
  id: string;
  agent_version: number;
  action: string;
  status: string;
  approval_request_id: string | null;
  created_at: string;
};

export async function listAgentCapabilities(): Promise<AgentCapabilitySummary[]> {
  return apiFetch<AgentCapabilitySummary[]>("/api/v1/agents/capabilities");
}

export async function createBuilderAgent(body: {
  key: string;
  name: string;
  description?: string;
  agent_type?: EngineeringAgentType;
  project_id?: string;
  instructions?: string;
  capability_keys?: string[];
}): Promise<AgentBuilderDetail> {
  return apiFetch<AgentBuilderDetail>("/api/v1/agents/builder", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "X-Actor-Id": "workspace-user" },
  });
}

export async function updateBuilderDraft(
  agentId: string,
  version: number,
  body: {
    instructions?: string;
    configuration_metadata?: Record<string, unknown>;
    capability_keys?: string[];
  },
): Promise<AgentBuilderDetail> {
  return apiFetch<AgentBuilderDetail>(`/api/v1/agents/${agentId}/versions/${version}/draft`, {
    method: "PUT",
    body: JSON.stringify(body),
    headers: { "X-Actor-Id": "workspace-user" },
  });
}

export async function validateBuilderVersion(
  agentId: string,
  version: number,
): Promise<AgentBuilderValidation> {
  return apiFetch<AgentBuilderValidation>(`/api/v1/agents/${agentId}/versions/${version}/validate`, {
    method: "POST",
  });
}

export async function testBuilderVersion(
  agentId: string,
  version: number,
  projectId: string,
  userRequest: string,
): Promise<AgentVersionTestSummary> {
  return apiFetch<AgentVersionTestSummary>(`/api/v1/agents/${agentId}/versions/${version}/test`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, user_request: userRequest }),
    headers: { "X-Actor-Id": "workspace-user" },
  });
}

export async function publishBuilderVersion(
  agentId: string,
  version: number,
  projectId: string,
): Promise<AgentBuilderPublicationSummary> {
  return apiFetch<AgentBuilderPublicationSummary>(
    `/api/v1/agents/${agentId}/versions/${version}/publish`,
    {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
      headers: { "X-Actor-Id": "workspace-user" },
    },
  );
}

export async function rollbackBuilderAgent(
  agentId: string,
  projectId: string,
  targetVersion: number,
): Promise<AgentBuilderPublicationSummary> {
  return apiFetch<AgentBuilderPublicationSummary>(`/api/v1/agents/${agentId}/rollback`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, target_version: targetVersion }),
    headers: { "X-Actor-Id": "workspace-user" },
  });
}

export async function listBuilderTests(
  agentId: string,
  version: number,
): Promise<{ tests: AgentVersionTestSummary[] }> {
  return apiFetch<{ tests: AgentVersionTestSummary[] }>(
    `/api/v1/agents/${agentId}/versions/${version}/tests`,
  );
}

export async function listBuilderPublications(
  agentId: string,
): Promise<{ publications: AgentBuilderPublicationSummary[] }> {
  return apiFetch<{ publications: AgentBuilderPublicationSummary[] }>(
    `/api/v1/agents/${agentId}/publications`,
  );
}

export async function listProjectAgents(projectId: string): Promise<AgentListResponse> {
  return apiFetch<AgentListResponse>(`/api/v1/agents?project_id=${projectId}`);
}

export async function getBuilderDetail(agentId: string, version: number): Promise<AgentBuilderDetail> {
  return apiFetch<AgentBuilderDetail>(`/api/v1/agents/${agentId}/builder?version=${version}`);
}
