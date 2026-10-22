import { mapAutocadResult } from "./autocad";
import { mapViewerData, storeyShears } from "./frame3d-viewer";
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
  Frame3dExport,
  Frame3dFoundation,
  Frame3dResults,
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

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function numberList(value: unknown): number[] {
  return Array.isArray(value)
    ? value.map((item) => parseOptionalNumber(item)).filter((item): item is number => item !== null)
    : [];
}

function recordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    : [];
}

function flatRows(value: unknown): Array<Record<string, string | number | null>> {
  return recordList(value).map((row) => {
    const out: Record<string, string | number | null> = {};
    for (const [key, v] of Object.entries(row)) {
      if (typeof v === "number" || typeof v === "string") {
        out[key] = v;
      } else if (v === null || v === undefined) {
        out[key] = null;
      } else if (Array.isArray(v)) {
        out[key] = v.filter((x) => typeof x === "string").join("; ");
      }
    }
    return out;
  });
}

function mapFrame3dDesign(raw: unknown): Frame3dResults["design"] {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  return {
    code: String(data.code ?? ""),
    status: String(data.status ?? ""),
    ductility: typeof data.ductility === "string" ? data.ductility : null,
    scwbNote: typeof data.scwb_note === "string" ? data.scwb_note : null,
    beams: flatRows(data.beams),
    columns: flatRows(data.columns),
    scwb: flatRows(data.scwb),
    clausesImplemented: stringList(data.clauses_implemented),
    clausesSimplified: stringList(data.clauses_simplified),
    message: typeof data.message === "string" ? data.message : null,
  };
}

export function mapFrame3dFoundation(raw: unknown): Frame3dFoundation | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  const overlap = data.overlap && typeof data.overlap === "object" ? (data.overlap as Record<string, unknown>) : {};
  return {
    status: String(data.status ?? ""),
    qaKpa: parseOptionalNumber(data.qa_kpa),
    qaAssumed: data.qa_assumed === true,
    qaNetKpa: parseOptionalNumber(data.qa_net_kpa),
    rows: flatRows(data.rows),
    minGapM: parseOptionalNumber(overlap.min_gap_m),
    coverage: parseOptionalNumber(overlap.coverage_ratio),
    recommendation: typeof overlap.recommendation === "string" ? overlap.recommendation : null,
    clausesImplemented: stringList(data.clauses_implemented),
    clausesSimplified: stringList(data.clauses_simplified),
  };
}

function mapFrame3dModal(raw: unknown): Frame3dResults["modal"] {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  const rs = data.response_spectrum && typeof data.response_spectrum === "object"
    ? (data.response_spectrum as Record<string, Record<string, unknown>>)
    : {};
  return {
    fundamentalPeriodS: parseOptionalNumber(data.T_fundamental_s),
    scaleRule: typeof data.scale_rule === "string" ? data.scale_rule : null,
    modes: recordList(data.modes).map((m) => ({
      mode: Number(m.mode ?? 0),
      periodS: parseOptionalNumber(m.T_s),
      massXPct: parseOptionalNumber(m.mass_x_pct),
      massYPct: parseOptionalNumber(m.mass_y_pct),
      massRzPct: parseOptionalNumber(m.mass_rz_pct),
    })),
    spectrum: Object.entries(rs).map(([direction, v]) => {
      const drifts = recordList(v.drift).map((d) => parseOptionalNumber(d.ratio_amplified_pct) ?? 0);
      return {
        direction,
        vDynamicKn: parseOptionalNumber(v.V_dynamic_kn),
        vStaticKn: parseOptionalNumber(v.V_static_kn),
        scaleFactor: parseOptionalNumber(v.scale_factor),
        maxDriftPct: drifts.length ? Math.max(...drifts) : null,
      };
    }),
  };
}

export function mapFrame3dExports(raw: unknown): Frame3dExport[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }
    const e = item as Record<string, unknown>;
    if (typeof e.format !== "string" || typeof e.filename !== "string") {
      return [];
    }
    return [
      {
        format: e.format,
        filename: e.filename,
        label: typeof e.label === "string" ? e.label : e.filename,
        requested: e.requested === true,
        notes: stringList(e.notes),
      },
    ];
  });
}

export function mapFrame3dResults(raw: unknown): Frame3dResults | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  if (data.kind !== "frame3d_analysis") {
    return null;
  }
  const geometry = data.geometry && typeof data.geometry === "object" ? (data.geometry as Record<string, unknown>) : {};
  const baseShear =
    data.base_shear_check && typeof data.base_shear_check === "object"
      ? (data.base_shear_check as Record<string, unknown>)
      : null;
  const columns = recordList(data.column_forces_by_storey);
  return {
    kind: "frame3d_analysis",
    status: typeof data.status === "string" ? data.status : "completed",
    message: typeof data.message === "string" ? data.message : null,
    disclaimer: typeof data.disclaimer === "string" ? data.disclaimer : null,
    code: typeof data.code === "string" ? data.code : null,
    seismicCode: typeof data.seismic_code === "string" ? data.seismic_code : null,
    designCode: typeof data.design_code === "string" ? data.design_code : null,
    fields: recordList(data.fields).map((item) => ({
      label: String(item.label ?? ""),
      value: String(item.value ?? ""),
      unit: item.unit ? String(item.unit) : null,
    })),
    drift: recordList(data.drift).map((item) => ({
      direction: String(item.direction ?? ""),
      storey: Number(item.storey ?? 0),
      driftElasticMm: parseOptionalNumber(item.drift_elastic_mm),
      ratioElasticPct: parseOptionalNumber(item.ratio_elastic_pct),
      ratioAmplifiedPct: parseOptionalNumber(item.ratio_amplified_pct),
    })),
    driftReferenceLimitPct: parseOptionalNumber(data.drift_reference_limit_pct),
    storeyForces: recordList(data.beam_forces_by_storey).map((item) => {
      const storey = Number(item.storey ?? 0);
      const column = columns.find((row) => Number(row.storey) === storey);
      return {
        storey,
        beamMNegKnM: parseOptionalNumber(item.M_neg_kn_m),
        beamMPosKnM: parseOptionalNumber(item.M_pos_kn_m),
        beamVKn: parseOptionalNumber(item.V_kn),
        columnPKn: column ? parseOptionalNumber(column.P_kn) : null,
      };
    }),
    baseShearStatus: baseShear && typeof baseShear.status === "string" ? baseShear.status : null,
    driftCheck: typeof data.drift_check === "string" ? data.drift_check : null,
    modal: mapFrame3dModal(data.modal),
    design: mapFrame3dDesign(data.design),
    lang: data.lang === "fa" ? "fa" : "en",
    viewer: mapViewerData(data.viewer),
    showFoundation: data.show_foundation === true,
    animateMode: typeof data.animate_mode === "number" ? data.animate_mode : null,
    storeyLateral: storeyShears(
      data.seismic && typeof data.seismic === "object"
        ? ((data.seismic as Record<string, unknown>).F_level_kn as Record<string, number> | undefined)
        : undefined,
    ),
    foundation: mapFrame3dFoundation(data.foundation),
    exports: mapFrame3dExports(data.exports),
    exportRequested: stringList(data.export_requested),
    modelFromProjectMemory: data.model_from_project_memory === true,
    inputs:
      data.inputs && typeof data.inputs === "object"
        ? { ...(data.inputs as Record<string, unknown>), _p: stringList(data.parsed_from_request) }
        : null,
    gridX: numberList(geometry.XS),
    gridY: numberList(geometry.YS),
    missing: stringList(data.missing_inputs),
    assumptions: stringList(data.assumptions),
    warnings: stringList(data.warnings),
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
    frame3dResults: mapFrame3dResults(metadata.engineering_results),
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
    autocadResult: mapAutocadResult(message.metadata.autocad_result),
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
