import type {
  AgentDefinitionSummary,
  AgentExecutionSummary,
  AgentExecutionUserView,
  EngineeringAgentType,
} from "./api";

export type ProgressStep = {
  key: AgentExecutionUserView["progress"] | "received" | "processing" | "review" | "done";
  label: string;
};

export type AssistantProfile = {
  id: string;
  title: string;
  description: string;
  capabilities: string[];
  status: "Available" | "In setup" | "Unavailable";
  agentType: EngineeringAgentType | null;
};

const ASSISTANT_CATALOG: Record<
  EngineeringAgentType,
  { title: string; description: string; capabilities: string[] }
> = {
  STRUCTURAL_MODELING_AGENT: {
    title: "Structural Modeling Assistant",
    description: "Build and revise structural models from project requirements and geometry inputs.",
    capabilities: ["Model setup", "Geometry updates", "System layout"],
  },
  LOAD_ASSESSMENT_AGENT: {
    title: "Load Assessment Assistant",
    description: "Review dead, live, and environmental loading assumptions for your project.",
    capabilities: ["Load combinations", "Code-based loading", "Load summaries"],
  },
  ANALYSIS_AGENT: {
    title: "Structural Analysis Assistant",
    description: "Run and interpret structural analysis workflows for frames, shells, and foundations.",
    capabilities: ["Analysis review", "Drift and stability", "Result summaries"],
  },
  CONCRETE_DESIGN_AGENT: {
    title: "Concrete Design Assistant",
    description: "Support concrete member and slab design checks aligned with project codes.",
    capabilities: ["Slab design", "Reinforcement review", "Concrete detailing"],
  },
  STEEL_DESIGN_AGENT: {
    title: "Steel Design Assistant",
    description: "Assist with steel member sizing, connections, and design decision documentation.",
    capabilities: ["Beam and column design", "Connection review", "Steel detailing"],
  },
  SEISMIC_AGENT: {
    title: "Seismic Design Assistant",
    description: "Evaluate seismic parameters, lateral systems, and earthquake design assumptions.",
    capabilities: ["Seismic loads", "Lateral system review", "Spectral considerations"],
  },
  VALIDATION_AGENT: {
    title: "Design Validation Assistant",
    description: "Validate project configuration, assumptions, and code compliance checkpoints.",
    capabilities: ["Code checks", "Assumption review", "Compliance summary"],
  },
  CAD_AGENT: {
    title: "CAD Coordination Assistant",
    description: "Coordinate drawing deliverables and CAD-related engineering documentation.",
    capabilities: ["Drawing review", "CAD coordination", "Deliverable tracking"],
  },
  REPORTING_AGENT: {
    title: "Engineering Report Assistant",
    description: "Prepare engineering summaries, decision history, and project deliverable reports.",
    capabilities: ["Report drafting", "Decision history", "Project summaries"],
  },
  DOCUMENT_INTERPRETATION_AGENT: {
    title: "Document Interpretation Assistant",
    description: "Interpret specifications, PDFs, and uploaded documents into actionable engineering context.",
    capabilities: ["Spec review", "Document extraction", "Requirement capture"],
  },
  PROMPT_GENERATION_AGENT: {
    title: "Request Planning Assistant",
    description: "Understand engineer requests and route work to the right specialist assistant.",
    capabilities: ["Request understanding", "Task routing", "Context planning"],
  },
};

const PROGRESS_LABELS: Record<AgentExecutionUserView["progress"], string> = {
  starting: "Received",
  in_progress: "Processing",
  awaiting_approval: "Review required",
  completed: "Completed",
  rejected: "Rejected",
  failed: "Failed",
  cancelled: "Cancelled",
};

const VALIDATION_LABELS: Record<string, string> = {
  PASS: "Checks passed",
  WARNING: "Review recommended",
  ERROR: "Issues found",
  NOT_RUN: "Not yet validated",
  REQUIRES_ENGINEER_REVIEW: "Engineer review recommended",
};

export function getProgressLabel(progress: AgentExecutionUserView["progress"]): string {
  return PROGRESS_LABELS[progress] ?? "In progress";
}

export function getValidationLabel(status: string | null | undefined): string | null {
  if (!status) {
    return null;
  }
  return VALIDATION_LABELS[status] ?? "Validation recorded";
}

export function getProgressSteps(current: AgentExecutionUserView["progress"]): ProgressStep[] {
  const steps: ProgressStep[] = [
    { key: "received", label: "Received" },
    { key: "processing", label: "Processing" },
    { key: "review", label: "Review required" },
    { key: "done", label: "Completed" },
  ];

  return steps.map((step) => ({
    ...step,
    label: step.label,
  }));
}

export function getActiveProgressIndex(progress: AgentExecutionUserView["progress"]): number {
  switch (progress) {
    case "starting":
      return 0;
    case "in_progress":
      return 1;
    case "awaiting_approval":
      return 2;
    case "completed":
    case "rejected":
    case "failed":
    case "cancelled":
      return 3;
    default:
      return 0;
  }
}

export function isTerminalProgress(progress: AgentExecutionUserView["progress"]): boolean {
  return progress === "completed" || progress === "rejected" || progress === "failed" || progress === "cancelled";
}

export function getTerminalStepLabel(progress: AgentExecutionUserView["progress"]): string {
  return getProgressLabel(progress);
}

export function buildAssistantProfiles(agents: AgentDefinitionSummary[]): AssistantProfile[] {
  const registeredByType = new Map(
    agents
      .filter((agent) => agent.agent_type)
      .map((agent) => [agent.agent_type as EngineeringAgentType, agent]),
  );

  const catalogTypes = Object.keys(ASSISTANT_CATALOG) as EngineeringAgentType[];

  return catalogTypes
    .filter((type) => type !== "PROMPT_GENERATION_AGENT")
    .map((type) => {
      const catalog = ASSISTANT_CATALOG[type];
      const registered = registeredByType.get(type);
      const status = registered
        ? registered.status === "ACTIVE"
          ? "Available"
          : registered.status === "DRAFT"
            ? "In setup"
            : "Unavailable"
        : "Available";

      return {
        id: registered?.id ?? type,
        title: catalog.title,
        description: registered?.description ?? catalog.description,
        capabilities: catalog.capabilities,
        status,
        agentType: type,
      };
    });
}

export type ApprovedExperienceRecord = {
  id: string;
  learning_scope: string;
  applicability: Record<string, unknown>;
  explanation: string;
  authority: string;
  provenance?: {
    learning_record_id?: string;
    task_id?: string;
    source_snapshot_id?: string;
  };
};

export type ApprovedEngineeringExperience = {
  heading: string;
  authority: string;
  records: ApprovedExperienceRecord[];
};

export function learningProvenancePath(projectId: string, recordId: string): string {
  return `/workspace/learning?project=${encodeURIComponent(projectId)}&record=${encodeURIComponent(recordId)}`;
}

export function approvedExperienceForExecution(
  execution: Pick<AgentExecutionSummary, "traceability_metadata">,
): ApprovedEngineeringExperience | null {
  const metadata = execution.traceability_metadata;
  if (!metadata || typeof metadata !== "object") {
    return null;
  }
  const experience = metadata.approved_engineering_experience;
  if (!experience || typeof experience !== "object") {
    return null;
  }
  const block = experience as Partial<ApprovedEngineeringExperience>;
  if (!Array.isArray(block.records) || block.records.length === 0) {
    return null;
  }
  return {
    heading: block.heading ?? "APPROVED ENGINEERING EXPERIENCE — CONTEXT ONLY",
    authority: block.authority ?? "CONTEXT_ONLY",
    records: block.records,
  };
}

export function summarizeExecution(execution: AgentExecutionSummary): {
  title: string;
  subtitle: string;
  hasResult: boolean;
  reportAvailable: boolean;
} {
  const summary = execution.user_view.summary ?? "Engineering request";
  const progress = getProgressLabel(execution.user_view.progress);
  const reportAvailable = Boolean(
    (execution as AgentExecutionSummary & { traceability_metadata?: { report_id?: string } })
      .traceability_metadata?.report_id,
  );

  return {
    title: summary,
    subtitle: `${progress} · ${formatDate(execution.created_at)}`,
    hasResult: isTerminalProgress(execution.user_view.progress) && Boolean(execution.user_view.final_result),
    reportAvailable,
  };
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getApprovalReviewPath(projectId: string, approvalRequestId: string): string {
  return `/workspace/agents?project=${projectId}&review=${approvalRequestId}`;
}
