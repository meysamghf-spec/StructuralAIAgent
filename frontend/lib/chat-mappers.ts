/** Map backend chat payloads to frontend chat domain types. */

import { mapToolExecution } from "./agent-run-sse";
import type {
  AgentExecutionStatus,
  AttachmentStatus,
  ChatAttachment,
  ChatMessage,
  Conversation,
  AgentRun,
  AgentRunStep,
  AgentRunStepState,
  AgentToolExecution,
  AciRcBeamResults,
  DemoEngineeringResults,
  DemoRcBeamInputs,
  DemoRcBeamNumericResults,
  EngineeringArtifact,
  EngineeringResult,
} from "./chat-types";

type BackendAttachment = {
  file_id: string;
  filename: string;
  file_type: string | null;
  content_type: string | null;
  status: string;
};

type BackendMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  attachments: BackendAttachment[];
  metadata: Record<string, unknown>;
  created_at: string;
};

type BackendConversation = {
  id: string;
  title: string;
  project_id: string | null;
  updated_at: string;
};

type BackendArtifact = {
  id: string;
  name: string;
  artifact_type: string;
  description?: string | null;
  href?: string | null;
};

function mapAttachmentStatus(status: string): AttachmentStatus {
  if (status === "uploading" || status === "processing") {
    return status;
  }
  if (status === "failed") {
    return "failed";
  }
  return "ready";
}

export function mapBackendAttachment(attachment: BackendAttachment): ChatAttachment {
  return {
    id: attachment.file_id,
    filename: attachment.filename,
    fileType: attachment.file_type,
    contentType: attachment.content_type,
    status: mapAttachmentStatus(attachment.status),
  };
}

function mapExecutionStatus(value: unknown): AgentExecutionStatus | null {
  if (typeof value !== "string") {
    return null;
  }
  const allowed: AgentExecutionStatus[] = [
    "queued",
    "in_progress",
    "awaiting_approval",
    "blocked",
    "completed",
    "failed",
    "rejected",
    "cancelled",
  ];
  return allowed.includes(value as AgentExecutionStatus)
    ? (value as AgentExecutionStatus)
    : "unknown";
}

function parseOptionalNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value.replace(/,/g, "").trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function mapDemoInputs(raw: unknown): DemoRcBeamInputs | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  return {
    spanM: parseOptionalNumber(data.span_m),
    uniformLoadKnM: parseOptionalNumber(data.uniform_load_kn_m),
    widthMm: parseOptionalNumber(data.width_mm),
    heightMm: parseOptionalNumber(data.height_mm),
    effectiveDepthMm: parseOptionalNumber(data.effective_depth_mm),
    fcMpa: parseOptionalNumber(data.fc_mpa),
    fyMpa: parseOptionalNumber(data.fy_mpa),
  };
}

function mapDemoNumericResults(raw: unknown): DemoRcBeamNumericResults | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  return {
    maxMomentKnM: parseOptionalNumber(data.max_moment_kn_m),
    maxShearKn: parseOptionalNumber(data.max_shear_kn),
  };
}

function mapDemoResults(raw: unknown): DemoEngineeringResults | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  if (data.kind !== "demo_rc_beam") {
    return null;
  }
  const fieldsRaw = Array.isArray(data.fields) ? data.fields : [];
  return {
    kind: String(data.kind),
    status: typeof data.status === "string" ? data.status : "completed",
    demo: Boolean(data.demo),
    disclaimer: typeof data.disclaimer === "string" ? data.disclaimer : null,
    code: typeof data.code === "string" ? data.code : null,
    fields: fieldsRaw
      .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
      .map((item) => ({
        label: String(item.label ?? ""),
        value: String(item.value ?? ""),
        unit: item.unit ? String(item.unit) : null,
      })),
    assumptions: Array.isArray(data.assumptions)
      ? data.assumptions.filter((item): item is string => typeof item === "string")
      : [],
    warnings: Array.isArray(data.warnings)
      ? data.warnings.filter((item): item is string => typeof item === "string")
      : [],
    inputs: mapDemoInputs(data.inputs),
    numericResults: mapDemoNumericResults(data.results),
  };
}

function mapAciBeamResults(raw: unknown): AciRcBeamResults | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  if (data.kind !== "aci_rc_beam") {
    return null;
  }
  const fieldsRaw = Array.isArray(data.fields) ? data.fields : [];
  const inputsRaw = data.inputs && typeof data.inputs === "object" ? (data.inputs as Record<string, unknown>) : {};
  const resultsRaw = data.results && typeof data.results === "object" ? (data.results as Record<string, unknown>) : {};
  return {
    kind: "aci_rc_beam",
    status: typeof data.status === "string" ? data.status : "completed",
    demo: Boolean(data.demo),
    disclaimer: typeof data.disclaimer === "string" ? data.disclaimer : null,
    code: typeof data.code === "string" ? data.code : null,
    pluginId: typeof data.plugin_id === "string" ? data.plugin_id : null,
    demandSource: typeof data.demand_source === "string" ? data.demand_source : null,
    inputUnits: typeof data.input_units === "string" ? data.input_units : null,
    internalUnits: typeof data.internal_units === "string" ? data.internal_units : null,
    outputUnits: typeof data.output_units === "string" ? data.output_units : null,
    fields: fieldsRaw
      .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
      .map((item) => ({
        label: String(item.label ?? ""),
        value: String(item.value ?? ""),
        unit: item.unit ? String(item.unit) : null,
      })),
    assumptions: Array.isArray(data.assumptions)
      ? data.assumptions.filter((item): item is string => typeof item === "string")
      : [],
    warnings: Array.isArray(data.warnings)
      ? data.warnings.filter((item): item is string => typeof item === "string")
      : [],
    missing: Array.isArray(data.missing)
      ? data.missing.filter((item): item is string => typeof item === "string")
      : [],
    inputs: {
      spanM: parseOptionalNumber(inputsRaw.span_m),
      uniformLoadKnM: parseOptionalNumber(inputsRaw.uniform_load_kn_m),
      widthMm: parseOptionalNumber(inputsRaw.width_mm),
      heightMm: parseOptionalNumber(inputsRaw.height_mm),
      effectiveDepthMm: parseOptionalNumber(inputsRaw.effective_depth_mm),
      fcMpa: parseOptionalNumber(inputsRaw.fc_mpa),
      fyMpa: parseOptionalNumber(inputsRaw.fy_mpa),
      asMm2: parseOptionalNumber(inputsRaw.as_mm2),
    },
    numericResults: {
      muKnM: parseOptionalNumber(resultsRaw.mu_kn_m) ?? parseOptionalNumber(
        data.demands && typeof data.demands === "object"
          ? (data.demands as Record<string, unknown>).mu_kn_m
          : null,
      ),
      vuKn: parseOptionalNumber(resultsRaw.vu_kn) ?? parseOptionalNumber(
        data.demands && typeof data.demands === "object"
          ? (data.demands as Record<string, unknown>).vu_kn
          : null,
      ),
      phiMnKnM: parseOptionalNumber(resultsRaw.phi_mn_kn_m),
      phiVcKn: parseOptionalNumber(resultsRaw.phi_vc_kn),
      flexureUtilization: parseOptionalNumber(resultsRaw.flexure_utilization),
      shearUtilization: parseOptionalNumber(resultsRaw.shear_utilization),
      governingUtilization: parseOptionalNumber(resultsRaw.governing_utilization),
      flexureOutcome: typeof resultsRaw.flexure_outcome === "string" ? resultsRaw.flexure_outcome : null,
      shearOutcome: typeof resultsRaw.shear_outcome === "string" ? resultsRaw.shear_outcome : null,
    },
  };
}

function mapEngineeringResult(metadata: Record<string, unknown>): EngineeringResult | null {
  if (metadata.mode !== "agent_execution") {
    return null;
  }

  const artifactsRaw = metadata.artifacts;
  const artifacts: EngineeringArtifact[] = Array.isArray(artifactsRaw)
    ? artifactsRaw
        .filter((item): item is BackendArtifact => typeof item === "object" && item !== null)
        .map((item) => ({
          id: String(item.id),
          name: String(item.name),
          artifactType: String(item.artifact_type),
          description: item.description ? String(item.description) : null,
          href: item.href ? String(item.href) : null,
        }))
    : [];

  const actionsRaw = metadata.actions;
  const actions = Array.isArray(actionsRaw)
    ? actionsRaw.filter(
        (item): item is { label: string; href: string } =>
          typeof item === "object" &&
          item !== null &&
          typeof (item as { label?: string }).label === "string" &&
          typeof (item as { href?: string }).href === "string",
      )
    : [];

  const statusEventsRaw = metadata.status_events;
  const statusEvents = Array.isArray(statusEventsRaw)
    ? statusEventsRaw.filter((item): item is string => typeof item === "string")
    : [];

  const approvalRequestId =
    typeof metadata.approval_request_id === "string" && metadata.approval_request_id.trim()
      ? metadata.approval_request_id
      : null;

  return {
    executionStatus: mapExecutionStatus(metadata.progress ?? metadata.execution_status),
    selectedCapability:
      typeof metadata.selected_capability === "string" ? metadata.selected_capability : null,
    requiresApproval: Boolean(metadata.requires_approval),
    approvalRequestId,
    statusEvents,
    artifacts,
    actions,
    demoResults: mapDemoResults(metadata.engineering_results),
    aciBeamResults: mapAciBeamResults(metadata.engineering_results),
    agentRun: mapAgentRun(metadata.agent_run),
  };
}

function mapStepState(value: unknown): AgentRunStepState {
  if (value === "complete" || value === "current" || value === "pending" || value === "error") {
    return value;
  }
  return "pending";
}

function mapAgentRun(raw: unknown): AgentRun | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  const stepsRaw = Array.isArray(data.steps) ? data.steps : [];
  const steps: AgentRunStep[] = stepsRaw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      key: String(item.key ?? ""),
      label: String(item.label ?? ""),
      state: mapStepState(item.state),
    }))
    .filter((item) => item.key && item.label);

  const toolsRaw = Array.isArray(data.tools) ? data.tools : [];
  const tools: AgentToolExecution[] = toolsRaw
    .map((item, index) => mapToolExecution(item, `tool-${index}`))
    .filter((item): item is AgentToolExecution => item !== null);

  const contextRaw = data.context && typeof data.context === "object" ? (data.context as Record<string, unknown>) : {};
  const filesRaw = Array.isArray(contextRaw.files) ? contextRaw.files : [];
  const errorRaw = data.error && typeof data.error === "object" ? (data.error as Record<string, unknown>) : null;

  return {
    lifecycle: typeof data.lifecycle === "string" ? data.lifecycle : "executing",
    currentStep: typeof data.current_step === "string" ? data.current_step : steps[0]?.key ?? "",
    progress: mapExecutionStatus(data.progress),
    selectedCapability: typeof data.selected_capability === "string" ? data.selected_capability : null,
    requiresApproval: Boolean(data.requires_approval),
    steps,
    tools,
    context: {
      conversation: Boolean(contextRaw.conversation),
      project: Boolean(contextRaw.project),
      projectId: typeof contextRaw.project_id === "string" ? contextRaw.project_id : null,
      conversationId: typeof contextRaw.conversation_id === "string" ? contextRaw.conversation_id : null,
      capability: typeof contextRaw.capability === "string" ? contextRaw.capability : null,
      files: filesRaw
        .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
        .map((item) => ({
          filename: String(item.filename ?? ""),
          fileType: typeof item.file_type === "string" ? item.file_type : null,
          availability: typeof item.availability === "string" ? item.availability : null,
        }))
        .filter((item) => item.filename),
      indexedDocumentCount:
        typeof contextRaw.indexed_document_count === "number" ? contextRaw.indexed_document_count : 0,
    },
    validationStatus: typeof data.validation_status === "string" ? data.validation_status : null,
    error:
      errorRaw && typeof errorRaw.title === "string"
        ? { title: errorRaw.title, reason: String(errorRaw.reason ?? "") }
        : null,
  };
}

export function mapBackendMessage(message: BackendMessage): ChatMessage {
  return {
    id: message.id,
    conversationId: message.conversation_id,
    role: message.role,
    content: message.content,
    timestamp: message.created_at,
    attachments: message.attachments.map(mapBackendAttachment),
    status: mapExecutionStatus(message.metadata.progress ?? message.metadata.execution_status),
    engineeringResult: mapEngineeringResult(message.metadata),
  };
}

export function mapBackendConversation(conversation: BackendConversation): Conversation {
  return {
    id: conversation.id,
    title: conversation.title,
    projectId: conversation.project_id,
    updatedAt: conversation.updated_at,
  };
}
