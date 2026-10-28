import { getAuthHeaders, getUploadAuthHeaders } from "./auth-session";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_BASE;
}

function buildJsonHeaders(extra?: HeadersInit): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...getAuthHeaders(),
    ...(extra ? (Object.fromEntries(new Headers(extra).entries()) as Record<string, string>) : {}),
  };
}

/** An API failure that keeps the machine-readable code (e.g. EMAIL_NOT_REGISTERED) next to the human message. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly details: Record<string, unknown>;
  readonly retryAfterSeconds: number | null;

  constructor(message: string, status: number, code: string | null, details: Record<string, unknown>, retryAfterSeconds: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: buildJsonHeaders(init?.headers),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Request failed (${response.status})`;
    const retryHeader = Number(response.headers?.get?.("retry-after"));
    const retryDetail = Number(body?.error?.details?.retry_after_seconds);
    throw new ApiError(
      message,
      response.status,
      typeof body?.error?.code === "string" ? body.error.code : null,
      (body?.error?.details as Record<string, unknown>) ?? {},
      Number.isFinite(retryDetail) && retryDetail > 0 ? retryDetail : Number.isFinite(retryHeader) && retryHeader > 0 ? retryHeader : null,
    );
  }

  if (response.status === 204) return undefined as T;
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
  | "PROMPT_GENERATION_AGENT"
  | "OPTIMIZATION_AGENT"
  | "STRUCTURAL_ENGINEERING_AGENT";

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
  input_request?: {
    user_request?: string;
    parameters?: Record<string, unknown>;
  };
  context_snapshot?: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  agent_result?: {
    structured_output?: Record<string, unknown>;
    generated_artifacts?: Array<Record<string, unknown>>;
    recommendations?: string[];
    validation_information?: Record<string, unknown>;
  } | null;
  error_metadata?: Record<string, unknown>;
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
  agent_definition_id?: string;
  requires_approval?: boolean;
  parameters?: {
    attachment_file_ids?: string[];
    operation?: string;
    apply_to_pem?: boolean;
    solver?: string;
    engineering_brief?: Record<string, string | number | boolean | null | { value: string | number | boolean | null; origin: string }>;
    architectural_brief?: Record<string, string | number | boolean | null | { value: string | number | boolean | null; origin: string }>;
  };
};

export type CurrentPemIdentity = {
  version: number;
  snapshotId: string;
  name: string | null;
};

export async function getCurrentPemIdentity(projectId: string): Promise<CurrentPemIdentity | null> {
  try {
    const body = await apiFetch<{
      version: number;
      snapshot_id: string;
      pem?: { metadata?: { name?: string | null } };
    }>(`/api/v1/projects/${projectId}/pem/current`);
    return {
      version: body.version,
      snapshotId: body.snapshot_id,
      name: body.pem?.metadata?.name ?? null,
    };
  } catch (error) {
    if (error instanceof Error && /not found/i.test(error.message)) {
      return null;
    }
    throw error;
  }
}

export async function createAgentExecution(
  body: CreateAgentExecutionRequest,
): Promise<AgentExecutionSummary> {
  return apiFetch<AgentExecutionSummary>("/api/v1/agent-executions", {
    method: "POST",
    body: JSON.stringify(body),
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
  decisionNote?: string,
): Promise<void> {
  await apiFetch(`/api/v1/approvals/${approvalRequestId}/approve?project_id=${projectId}`, {
    method: "POST",
    body: JSON.stringify({
      approver: "authenticated-user",
      decision_note: decisionNote ?? null,
    }),
  });
}

export async function rejectAgentRequest(
  projectId: string,
  approvalRequestId: string,
  rejectionReason: string,
): Promise<ApprovalSummary> {
  return apiFetch<ApprovalSummary>(`/api/v1/approvals/${approvalRequestId}/reject?project_id=${projectId}`, {
    method: "POST",
    body: JSON.stringify({
      approver: "authenticated-user",
      rejection_reason: rejectionReason,
    }),
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
  metadata?: Record<string, unknown>;
  revision_outcome?: string | null;
  next_approval_id?: string | null;
  revision_message?: string | null;
};

export type RevisionChange = { key: string; old: unknown; new: unknown };

/** Engineering-run approvals grouped into revision chains (root -> rev 2 -> ...), newest chain first. */
export function revisionChains(items: ApprovalSummary[]): ApprovalSummary[][] {
  const runs = items.filter((a) => a.metadata && typeof a.metadata.module_kind === "string");
  const byRoot = new Map<string, ApprovalSummary[]>();
  for (const a of runs) {
    const root = String(a.metadata?.root_approval_id ?? a.id);
    byRoot.set(root, [...(byRoot.get(root) ?? []), a]);
  }
  return [...byRoot.values()]
    .map((c) => c.sort((x, y) => Number(x.metadata?.revision ?? 1) - Number(y.metadata?.revision ?? 1)))
    .sort((a, b) => (b[b.length - 1].requested_at > a[a.length - 1].requested_at ? 1 : -1));
}

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

export async function getApprovalRequest(projectId: string, approvalRequestId: string): Promise<ApprovalSummary> {
  return apiFetch<ApprovalSummary>(`/api/v1/approvals/${approvalRequestId}?project_id=${projectId}`);
}

export type ProjectApprovalSummary = {
  state: "approved" | "pending" | "needs_revision" | "no_runs";
  project_approved: boolean;
  counts: { pending: number; approved: number; rejected: number; cancelled: number; total: number; chains: number };
  blockers: { code: string; en: string; fa: string }[];
};

/** Why a project is (not) approved, derived from the real approval items. */
export async function getProjectApprovalSummary(projectId: string): Promise<ProjectApprovalSummary> {
  return apiFetch<ProjectApprovalSummary>(`/api/v1/approvals/summary?project_id=${projectId}`);
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
    }),
  });
}

export type ReportVersionDetail = ReportVersionSummary & {
  project_id?: string;
  output_format?: string;
  traceability_metadata?: Record<string, unknown>;
};

/** One generated version of a report (existing GET /reports/{id}/versions/{version}). */
export async function getReportVersion(
  projectId: string,
  reportId: string,
  version: number,
): Promise<ReportVersionDetail> {
  return apiFetch<ReportVersionDetail>(
    `/api/v1/reports/${reportId}/versions/${version}?project_id=${projectId}`,
  );
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
      }),
    },
  );
}

export type ProjectFileSummary = {
  id: string;
  project_id?: string;
  filename: string;
  content_type?: string | null;
  file_type: string;
  file_version?: number;
  parsing_status: string;
  extraction_status: string;
  upload_time: string;
  created_at: string;
  updated_at?: string;
  byte_length?: number | null;
};

export type ProjectFileListResponse = {
  project_id: string;
  files: ProjectFileSummary[];
};

export async function listProjectFiles(projectId: string): Promise<ProjectFileListResponse> {
  return apiFetch<ProjectFileListResponse>(`/api/v1/projects/${projectId}/files`);
}

export async function downloadProjectFile(
  projectId: string,
  fileId: string,
  filename: string,
): Promise<void> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/projects/${projectId}/files/${fileId}/content`,
    {
      headers: getAuthHeaders(),
      cache: "no-store",
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Download failed (${response.status})`;
    throw new Error(message);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

export async function downloadFrame3dExport(
  format: string,
  inputs: Record<string, unknown>,
  filename: string,
): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/frame3d/export`, {
    method: "POST",
    headers: buildJsonHeaders(),
    body: JSON.stringify({ format, inputs }),
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : typeof body?.detail === "string"
          ? body.detail
          : `Export failed (${response.status})`;
    throw new Error(message);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

export async function uploadProjectFile(projectId: string, file: File): Promise<ProjectFileSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${getApiBaseUrl()}/api/v1/projects/${projectId}/files`, {
    method: "POST",
    body: formData,
    headers: getUploadAuthHeaders(),
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

export type LearningProvenance = {
  learning_record_id: string;
  task_id: string;
  agent_id: string;
  source_snapshot_id: string;
  source_element_ids: string[];
  source_element_type: string;
  engineering_result_id: string;
  qa_result: string;
  human_decision: string;
  learning_scope: string;
  project_id: string;
  owner_account_id: string;
};

export type LearningRecordSummary = {
  id: string;
  project_id: string | null;
  owner_account_id: string;
  agent_id: string | null;
  task_id: string | null;
  approval_status: string;
  learning_scope: string;
  engineering_reason: string | null;
  validation_result: string;
  applicability: Record<string, unknown>;
  provenance: LearningProvenance;
  reviewed_by: string | null;
  created_at: string;
};

export type LearningListResponse = {
  records: LearningRecordSummary[];
};

export type LearningUseSummary = {
  learning_record_id: string;
  explanation: string;
  created_at: string;
};

export async function listLearningRecords(projectId: string): Promise<LearningListResponse> {
  return apiFetch<LearningListResponse>(`/api/v1/projects/${projectId}/learning`);
}

export async function reviewLearningRecord(projectId: string, recordId: string): Promise<LearningRecordSummary> {
  return apiFetch<LearningRecordSummary>(`/api/v1/projects/${projectId}/learning/${recordId}/review`, {
    method: "POST",
  });
}

export async function approveLearningRecord(projectId: string, recordId: string): Promise<LearningRecordSummary> {
  return apiFetch<LearningRecordSummary>(`/api/v1/projects/${projectId}/learning/${recordId}/approve`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function rejectLearningRecord(
  projectId: string,
  recordId: string,
  reason: string,
): Promise<LearningRecordSummary> {
  return apiFetch<LearningRecordSummary>(`/api/v1/projects/${projectId}/learning/${recordId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function getLearningUsedByTask(
  projectId: string,
  taskId: string,
): Promise<{ task_id: string; uses: LearningUseSummary[] }> {
  return apiFetch(`/api/v1/projects/${projectId}/learning/tasks/${taskId}`);
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
    seismic_standard?: string | null;
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
    created_by?: string | null;
    created_at?: string;
    capabilities: AgentCapabilitySummary[];
  };
  validation: AgentBuilderValidation;
  lifecycle?: string;
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
  purpose?: string;
  engineering_domain?: string;
  agent_type?: EngineeringAgentType;
  project_id?: string;
  instructions?: string;
  capability_keys?: string[];
  task_types?: string[];
  element_types?: string[];
  supported_codes?: string[];
  allowed_tools?: string[];
  input_contract?: Record<string, unknown>;
  output_contract?: Record<string, unknown>;
  change_summary?: string;
}): Promise<AgentBuilderDetail> {
  return apiFetch<AgentBuilderDetail>("/api/v1/agents/builder", {
    method: "POST",
    body: JSON.stringify(body),
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

export async function createSuccessorVersion(
  agentId: string,
  sourceVersion: number,
  changeSummary: string,
): Promise<AgentBuilderDetail> {
  return apiFetch<AgentBuilderDetail>(`/api/v1/agents/${agentId}/successor`, {
    method: "POST",
    body: JSON.stringify({ source_version: sourceVersion, change_summary: changeSummary }),
  });
}

export async function duplicateBuilderAgent(
  agentId: string,
  projectId: string,
  name?: string,
): Promise<AgentBuilderDetail> {
  return apiFetch<AgentBuilderDetail>(`/api/v1/agents/${agentId}/duplicate`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, name }),
  });
}

export async function disableBuilderAgent(agentId: string, projectId: string): Promise<AgentDefinitionSummary> {
  return apiFetch<AgentDefinitionSummary>(`/api/v1/agents/${agentId}/disable`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

export async function archiveBuilderAgent(agentId: string): Promise<AgentDefinitionSummary> {
  return apiFetch<AgentDefinitionSummary>(`/api/v1/agents/${agentId}/archive`, {
    method: "POST",
  });
}


/** Fetch a frame3d export (e2k/f2k/s2k/dxf) as text, for in-page viewers. */
export async function fetchFrame3dExportText(format: string, inputs: Record<string, unknown>): Promise<string> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/frame3d/export`, {
    method: "POST",
    headers: buildJsonHeaders(),
    body: JSON.stringify({ format, inputs }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  return response.text();
}

/** Fetch a project file as a Blob (for inline preview). */
export async function fetchProjectFileBlob(projectId: string, fileId: string): Promise<Blob> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/projects/${projectId}/files/${fileId}/content`, {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Preview failed (${response.status})`);
  return response.blob();
}

/** Submit a chat/workspace engineering result (e.g. 3D frame + Mabhas 9 design) for human approval. */
export async function createApprovalRequest(
  projectId: string,
  request: { targetAction: string; summary: string; targetType?: "DESIGN_DECISION" | "MODEL_CHANGE"; metadata?: Record<string, unknown> },
): Promise<ApprovalSummary> {
  return apiFetch<ApprovalSummary>("/api/v1/approvals", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      requester: "authenticated-user",
      target_type: request.targetType ?? "DESIGN_DECISION",
      target_action: request.targetAction,
      summary: request.summary,
      metadata: request.metadata ?? {},
    }),
  });
}

/** Same endpoint as uploadProjectFile, via XHR so the UI can show upload progress (0–1). */
export function uploadProjectFileWithProgress(
  projectId: string,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<ProjectFileSummary> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${getApiBaseUrl()}/api/v1/projects/${projectId}/files`);
    const headers = getUploadAuthHeaders() as Record<string, string>;
    for (const [k, v] of Object.entries(headers ?? {})) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      let body: any = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) { onProgress(1); resolve(body as ProjectFileSummary); return; }
      const msg = typeof body?.error?.message === "string" ? body.error.message
        : xhr.status === 413 ? "File is too large for the server (limit 100 MB)." : `Upload failed (${xhr.status})`;
      reject(new Error(msg));
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}
