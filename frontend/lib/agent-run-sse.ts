/** Parse and apply agent-run SSE events. No timers; events come from the backend. */

import type {
  AgentRun,
  AgentRunContext,
  AgentRunError,
  AgentRunStep,
  AgentRunStepState,
  AgentToolAction,
  AgentToolArtifactRef,
  AgentToolDetail,
  AgentToolExecution,
  AgentToolFile,
} from "./chat-types";

export type AgentRunSseEvent = {
  type: string;
  data: Record<string, unknown>;
};

export const AGENT_RUN_SSE_EVENTS = {
  started: "agent_run.started",
  step: "agent_run.step",
  tool: "agent_run.tool",
  context: "agent_run.context",
  validation: "agent_run.validation",
  approvalRequired: "agent_run.approval_required",
  completed: "agent_run.completed",
  failed: "agent_run.failed",
  token: "agent_run.token",
} as const;

export function emptyAgentRun(overrides: Partial<AgentRun> = {}): AgentRun {
  return {
    lifecycle: "planning",
    currentStep: "understand",
    progress: "queued",
    selectedCapability: null,
    requiresApproval: false,
    steps: [],
    tools: [],
    context: {
      conversation: true,
      project: false,
      projectId: null,
      conversationId: null,
      capability: null,
      files: [],
      indexedDocumentCount: 0,
    },
    validationStatus: null,
    error: null,
    ...overrides,
  };
}

export function parseSseBlock(block: string): AgentRunSseEvent | null {
  const trimmed = block.trim();
  if (!trimmed) {
    return null;
  }
  let type = "";
  const dataLines: string[] = [];
  for (const rawLine of trimmed.split(/\r?\n/)) {
    if (rawLine.startsWith("event:")) {
      type = rawLine.slice(6).trim();
    } else if (rawLine.startsWith("data:")) {
      dataLines.push(rawLine.slice(5).trimStart());
    }
  }
  if (!type || dataLines.length === 0) {
    return null;
  }
  try {
    const parsed = JSON.parse(dataLines.join("\n"));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }
    return { type, data: parsed as Record<string, unknown> };
  } catch {
    return null;
  }
}

export function isTerminalAgentRunEvent(type: string, data: Record<string, unknown>): boolean {
  if (type !== AGENT_RUN_SSE_EVENTS.completed && type !== AGENT_RUN_SSE_EVENTS.failed && type !== AGENT_RUN_SSE_EVENTS.approvalRequired) {
    return false;
  }
  return Boolean(data.assistant_message);
}

function asStepState(value: unknown): AgentRunStepState {
  if (value === "complete" || value === "current" || value === "pending" || value === "error") {
    return value;
  }
  return "pending";
}

function upsertStep(run: AgentRun, step: AgentRunStep): AgentRun {
  const index = run.steps.findIndex((item) => item.key === step.key);
  const steps = [...run.steps];
  if (index >= 0) {
    steps[index] = { ...steps[index], ...step };
  } else {
    steps.push(step);
  }
  return {
    ...run,
    steps,
    currentStep: step.state === "current" || step.state === "error" ? step.key : run.currentStep,
    lifecycle: step.state === "error" ? "failed" : run.lifecycle,
  };
}

function mergeDetails(existing: AgentToolDetail[], incoming: AgentToolDetail[]): AgentToolDetail[] {
  if (incoming.length === 0) {
    return existing;
  }
  const merged = new Map<string, AgentToolDetail>();
  for (const detail of existing) {
    merged.set(detail.key || detail.label, detail);
  }
  for (const detail of incoming) {
    merged.set(detail.key || detail.label, detail);
  }
  return Array.from(merged.values());
}

function mergeFiles(existing: AgentToolFile[] | undefined, incoming: AgentToolFile[] | undefined): AgentToolFile[] | undefined {
  if (!incoming?.length) {
    return existing;
  }
  const merged = new Map<string, AgentToolFile>();
  for (const file of existing ?? []) {
    merged.set(file.filename, file);
  }
  for (const file of incoming) {
    merged.set(file.filename, { ...merged.get(file.filename), ...file });
  }
  return Array.from(merged.values());
}

function mergeArtifacts(
  existing: AgentToolArtifactRef[] | undefined,
  incoming: AgentToolArtifactRef[] | undefined,
): AgentToolArtifactRef[] | undefined {
  if (!incoming?.length) {
    return existing;
  }
  const merged = new Map<string, AgentToolArtifactRef>();
  for (const artifact of existing ?? []) {
    merged.set(artifact.id, artifact);
  }
  for (const artifact of incoming) {
    merged.set(artifact.id, { ...merged.get(artifact.id), ...artifact });
  }
  return Array.from(merged.values());
}

function mergeOperations(existing: string[] | undefined, incoming: string[] | undefined): string[] | undefined {
  if (!incoming?.length && !existing?.length) {
    return existing;
  }
  return Array.from(new Set([...(existing ?? []), ...(incoming ?? [])]));
}

function upsertTool(run: AgentRun, tool: AgentToolExecution): AgentRun {
  const index = run.tools.findIndex((item) => item.id === tool.id);
  const tools = [...run.tools];
  if (index >= 0) {
    const current = tools[index];
    tools[index] = {
      ...current,
      ...tool,
      details: mergeDetails(current.details, tool.details),
      files: mergeFiles(current.files, tool.files),
      artifacts: mergeArtifacts(current.artifacts, tool.artifacts),
      operations: mergeOperations(current.operations, tool.operations),
      counts: { ...(current.counts ?? {}), ...(tool.counts ?? {}) },
      actions: tool.actions?.length ? tool.actions : current.actions,
      error: tool.error ?? current.error,
    };
  } else {
    tools.push(tool);
  }
  return { ...run, tools };
}

function mapContext(raw: unknown, fallback: AgentRunContext): AgentRunContext {
  if (!raw || typeof raw !== "object") {
    return fallback;
  }
  const data = raw as Record<string, unknown>;
  const filesRaw = Array.isArray(data.files) ? data.files : [];
  return {
    conversation: data.conversation !== undefined ? Boolean(data.conversation) : fallback.conversation,
    project: data.project !== undefined ? Boolean(data.project) : fallback.project,
    projectId: typeof data.project_id === "string" ? data.project_id : fallback.projectId,
    conversationId: typeof data.conversation_id === "string" ? data.conversation_id : fallback.conversationId,
    capability: typeof data.capability === "string" ? data.capability : fallback.capability,
    files: filesRaw
      .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
      .map((item) => ({
        filename: String(item.filename ?? ""),
        fileType: typeof item.file_type === "string" ? item.file_type : null,
        availability: typeof item.availability === "string" ? item.availability : null,
      }))
      .filter((item) => item.filename),
    indexedDocumentCount:
      typeof data.indexed_document_count === "number" ? data.indexed_document_count : fallback.indexedDocumentCount,
  };
}

function asOptionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function mapToolDetails(raw: unknown): AgentToolDetail[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      key: asOptionalString(item.key) ?? undefined,
      label: String(item.label ?? ""),
      state: asStepState(item.state),
    }))
    .filter((item) => item.label);
}

function mapToolFiles(raw: unknown): AgentToolFile[] | undefined {
  if (!Array.isArray(raw)) {
    return undefined;
  }
  const files = raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      filename: String(item.filename ?? ""),
      fileType: asOptionalString(item.file_type ?? item.fileType),
      availability: asOptionalString(item.availability),
      pageCount: asFiniteNumber(item.page_count ?? item.pageCount),
    }))
    .filter((item) => item.filename);
  return files.length > 0 ? files : undefined;
}

function mapToolArtifacts(raw: unknown): AgentToolArtifactRef[] | undefined {
  if (!Array.isArray(raw)) {
    return undefined;
  }
  const artifacts = raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item, index) => ({
      id: String(item.id ?? `artifact-${index}`),
      name: String(item.name ?? item.artifact_type ?? "Artifact"),
      artifactType: String(item.artifact_type ?? item.artifactType ?? "artifact"),
    }))
    .filter((item) => item.name);
  return artifacts.length > 0 ? artifacts : undefined;
}

function mapToolActions(raw: unknown): AgentToolAction[] | undefined {
  if (!Array.isArray(raw)) {
    return undefined;
  }
  const actions = raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .filter((item) => typeof item.label === "string" && typeof item.href === "string")
    .map((item) => ({ label: String(item.label), href: String(item.href) }))
    .filter((item) => item.label && item.href.startsWith("/"));
  return actions.length > 0 ? actions : undefined;
}

function mapToolCounts(raw: unknown): Record<string, number> | undefined {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return undefined;
  }
  const counts: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof value === "number" && Number.isFinite(value)) {
      counts[key] = value;
    }
  }
  return Object.keys(counts).length > 0 ? counts : undefined;
}

function mapToolError(raw: unknown): AgentRunError | null | undefined {
  if (raw == null) {
    return undefined;
  }
  if (typeof raw !== "object") {
    return undefined;
  }
  const data = raw as Record<string, unknown>;
  const title = asOptionalString(data.title);
  const reason = asOptionalString(data.reason);
  if (!title && !reason) {
    return undefined;
  }
  return {
    title: title ?? "Tool execution failed",
    reason: reason ?? "The tool could not complete this engineering step.",
  };
}

export function mapToolExecution(raw: unknown, fallbackId = "tool"): AgentToolExecution | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  const operations = Array.isArray(data.operations)
    ? data.operations.filter((item): item is string => typeof item === "string")
    : undefined;
  return {
    id: String(data.id ?? fallbackId),
    name: String(data.name ?? "Engineering action"),
    capability: typeof data.capability === "string" ? data.capability : null,
    status: asStepState(data.status),
    operation: asOptionalString(data.operation),
    operations,
    details: mapToolDetails(data.details),
    files: mapToolFiles(data.files),
    artifacts: mapToolArtifacts(data.artifacts),
    counts: mapToolCounts(data.counts),
    actions: mapToolActions(data.actions),
    error: mapToolError(data.error),
  };
}

export function applyAgentRunEvent(run: AgentRun | null, event: AgentRunSseEvent): AgentRun {
  const current = run ?? emptyAgentRun();
  if (event.type === AGENT_RUN_SSE_EVENTS.started) {
    return {
      ...current,
      lifecycle: "planning",
      context: {
        ...current.context,
        conversation: true,
        conversationId: typeof event.data.conversation_id === "string" ? event.data.conversation_id : current.context.conversationId,
      },
    };
  }
  if (event.type === AGENT_RUN_SSE_EVENTS.step) {
    const stepId = typeof event.data.step_id === "string" ? event.data.step_id : "";
    const name = typeof event.data.name === "string" ? event.data.name : stepId;
    if (!stepId) {
      return current;
    }
    return upsertStep(current, { key: stepId, label: name, state: asStepState(event.data.status) });
  }
  if (event.type === AGENT_RUN_SSE_EVENTS.tool) {
    const tool = mapToolExecution(event.data.tool ?? event.data);
    return tool ? upsertTool(current, tool) : current;
  }
  if (event.type === AGENT_RUN_SSE_EVENTS.context) {
    return { ...current, context: mapContext(event.data.context, current.context), lifecycle: "executing" };
  }
  if (event.type === AGENT_RUN_SSE_EVENTS.validation) {
    return {
      ...current,
      validationStatus: typeof event.data.validation_status === "string" ? event.data.validation_status : current.validationStatus,
    };
  }
  if (event.type === AGENT_RUN_SSE_EVENTS.approvalRequired) {
    return {
      ...current,
      lifecycle: "waiting_for_approval",
      requiresApproval: true,
      progress: "awaiting_approval",
    };
  }
  if (event.type === AGENT_RUN_SSE_EVENTS.completed) {
    return { ...current, lifecycle: "completed", progress: "completed" };
  }
  if (event.type === AGENT_RUN_SSE_EVENTS.failed) {
    const errorRaw = event.data.error;
    const error =
      errorRaw && typeof errorRaw === "object"
        ? {
            title: String((errorRaw as { title?: string }).title ?? "Engineering workflow failed"),
            reason: String((errorRaw as { reason?: string }).reason ?? "The agent could not complete this engineering step."),
          }
        : {
            title: "Engineering workflow failed",
            reason: "The agent could not complete this engineering step.",
          };
    return { ...current, lifecycle: "failed", progress: "failed", error };
  }
  return current;
}

export function agentRunToMetadata(run: AgentRun): Record<string, unknown> {
  return {
    lifecycle: run.lifecycle,
    current_step: run.currentStep,
    progress: run.progress,
    selected_capability: run.selectedCapability,
    requires_approval: run.requiresApproval,
    steps: run.steps,
    tools: run.tools.map((tool) => ({
      id: tool.id,
      name: tool.name,
      capability: tool.capability,
      status: tool.status,
      operation: tool.operation,
      operations: tool.operations,
      details: tool.details,
      files: tool.files?.map((file) => ({
        filename: file.filename,
        file_type: file.fileType,
        availability: file.availability,
        page_count: file.pageCount,
      })),
      artifacts: tool.artifacts?.map((artifact) => ({
        id: artifact.id,
        name: artifact.name,
        artifact_type: artifact.artifactType,
      })),
      counts: tool.counts,
      actions: tool.actions,
      error: tool.error,
    })),
    context: {
      conversation: run.context.conversation,
      project: run.context.project,
      project_id: run.context.projectId,
      conversation_id: run.context.conversationId,
      capability: run.context.capability,
      files: run.context.files.map((file) => ({
        filename: file.filename,
        file_type: file.fileType,
        availability: file.availability,
      })),
      indexed_document_count: run.context.indexedDocumentCount,
    },
    validation_status: run.validationStatus,
    error: run.error,
  };
}
