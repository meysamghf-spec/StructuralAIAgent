import type { EngineeringAgentType } from "./api";

export type BuilderLifecycleStage =
  | "draft"
  | "tested"
  | "review"
  | "active"
  | "inactive";

const ASSISTANT_TYPE_LABELS: Record<EngineeringAgentType, string> = {
  STRUCTURAL_MODELING_AGENT: "Structural modeling",
  LOAD_ASSESSMENT_AGENT: "Load assessment",
  ANALYSIS_AGENT: "Structural analysis",
  CONCRETE_DESIGN_AGENT: "Concrete design",
  STEEL_DESIGN_AGENT: "Steel design",
  SEISMIC_AGENT: "Seismic design",
  VALIDATION_AGENT: "Design validation",
  CAD_AGENT: "Drawings & CAD",
  REPORTING_AGENT: "Engineering reports",
  DOCUMENT_INTERPRETATION_AGENT: "Document review",
  PROMPT_GENERATION_AGENT: "Request planning",
  OPTIMIZATION_AGENT: "Optimization",
  STRUCTURAL_ENGINEERING_AGENT: "Structural engineering",
};

const VERSION_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  INACTIVE: "Inactive",
  ARCHIVED: "Previous version",
};

const PUBLICATION_STATUS_LABELS: Record<string, string> = {
  PENDING_APPROVAL: "Awaiting review",
  COMPLETED: "Completed",
  REJECTED: "Rejected",
  CANCELLED: "Cancelled",
  APPROVED: "Approved",
};

export function getAssistantTypeLabel(type: string | null | undefined): string {
  if (!type) {
    return "Not selected";
  }
  return ASSISTANT_TYPE_LABELS[type as EngineeringAgentType] ?? "Specialist assistant";
}

export function getVersionStatusLabel(status: string): string {
  return VERSION_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getPublicationStatusLabel(status: string): string {
  return PUBLICATION_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getLifecycleStage(
  versionStatus: string,
  hasTests: boolean,
  publicationStatus?: string | null,
): BuilderLifecycleStage {
  if (versionStatus === "ACTIVE") {
    return "active";
  }
  if (versionStatus === "INACTIVE") {
    return "inactive";
  }
  if (publicationStatus === "PENDING_APPROVAL") {
    return "review";
  }
  if (hasTests) {
    return "tested";
  }
  return "draft";
}

export type ProductLifecycle = "DRAFT" | "REVIEW" | "APPROVED" | "PUBLISHED" | "ARCHIVED";

export function getProductLifecycle(
  versionStatus: string,
  publicationStatus?: string | null,
  approvalStatus?: string | null,
): ProductLifecycle {
  if (versionStatus === "ARCHIVED") {
    return "ARCHIVED";
  }
  if (versionStatus === "ACTIVE") {
    return "PUBLISHED";
  }
  if (versionStatus === "INACTIVE") {
    return approvalStatus === "APPROVED" ? "APPROVED" : "ARCHIVED";
  }
  if (publicationStatus === "PENDING_APPROVAL") {
    return "REVIEW";
  }
  if (approvalStatus === "APPROVED") {
    return "APPROVED";
  }
  return "DRAFT";
}

export function getProductLifecycleLabel(lifecycle: string): string {
  switch (lifecycle) {
    case "DRAFT":
      return "Draft";
    case "REVIEW":
      return "Review";
    case "APPROVED":
      return "Approved";
    case "PUBLISHED":
      return "Published";
    case "ARCHIVED":
      return "Archived";
    default:
      return lifecycle;
  }
}

export function getLifecycleLabel(stage: BuilderLifecycleStage): string {
  switch (stage) {
    case "draft":
      return "Draft";
    case "tested":
      return "Tested";
    case "review":
      return "Review";
    case "active":
      return "Active";
    case "inactive":
      return "Inactive";
    default:
      return "Draft";
  }
}

export const AVAILABLE_TOOL_OPTIONS = [
  { id: "project.validate", label: "Project validation" },
  { id: "project.context", label: "Project context" },
  { id: "engineering.analysis.run", label: "Structural analysis" },
  { id: "engineering.design.run", label: "Member design checks" },
  { id: "code.lookup", label: "Code lookup" },
  { id: "report.generate", label: "Report generation" },
  { id: "document.extract", label: "Document extraction" },
  { id: "integration.autocad", label: "CAD coordination" },
];
