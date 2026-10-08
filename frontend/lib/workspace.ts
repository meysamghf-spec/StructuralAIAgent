export function formatWorkspaceDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const APPROVAL_STATUS_LABELS: Record<string, string> = {
  PENDING: "Awaiting review",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  CANCELLED: "Cancelled",
  NOT_REQUIRED: "Not required",
};

const MEMORY_TYPE_LABELS: Record<string, string> = {
  DECISION: "Decision",
  ASSUMPTION: "Assumption",
  REJECTION: "Rejection",
  REQUIREMENT: "Requirement",
  DESIGN_CHOICE: "Design choice",
  MODEL_VERSION: "Model version",
  EXTRACTED_INFORMATION: "Extracted information",
  VALIDATION_RESULT: "Validation result",
  CONVERSATION: "Conversation",
  REVISION: "Revision",
};

const REPORT_TYPE_LABELS: Record<string, string> = {
  STRUCTURAL_DESIGN: "Structural design report",
  ANALYSIS: "Analysis report",
  VALIDATION: "Validation report",
  PROJECT_SUMMARY: "Project summary",
  DECISION_HISTORY: "Decision history",
};

const REPORT_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  GENERATING: "Generating",
  COMPLETED: "Ready",
  FAILED: "Failed",
};

const FILE_STATUS_LABELS: Record<string, string> = {
  PENDING: "Waiting to process",
  IN_PROGRESS: "Processing",
  COMPLETE: "Processed",
  COMPLETED: "Processed",
  FAILED: "Processing failed",
  SKIPPED: "Skipped",
  NOT_APPLICABLE: "Not applicable",
};

const TRACE_RELATIONSHIP_LABELS: Record<string, string> = {
  REQUIREMENT_TO_SOURCE: "Requirement linked to source",
  SOURCE_TO_MEMORY: "Source indexed to memory",
  MEMORY_TO_DECISION: "Memory informed decision",
  DECISION_TO_APPROVAL: "Decision sent for approval",
  APPROVAL_TO_MODEL: "Approval applied to model",
  MODEL_TO_ANALYSIS: "Model used in analysis",
  ANALYSIS_TO_RESULT: "Analysis produced validated results",
  RESULT_TO_DESIGN: "Results used in design",
  RESULT_TO_OPTIMIZATION: "Results used in optimization",
  MODEL_TO_EXTERNAL_MODEL: "Model exported to solver",
  EXTERNAL_MODEL_TO_RESULT: "Solver model produced results",
  INTEGRATION_EXECUTION_TO_RESULT: "Solver run produced results",
  MODEL_TO_DRAWING: "Model used for CAD drawing",
  DRAWING_TO_REPORT: "Drawing included in report",
  OPTIMIZATION_TO_REPORT: "Optimization included in report",
  DESIGN_TO_REPORT: "Design included in report",
  REQUEST_TO_AGENT_EXECUTION: "Request started assistant work",
  AGENT_EXECUTION_TO_RESULT: "Assistant produced result",
  AGENT_RESULT_TO_VALIDATION: "Result validated",
  AGENT_RESULT_TO_APPROVAL: "Result sent for approval",
  APPROVAL_TO_AGENT_RESULT: "Approval finalized result",
  AGENT_RESULT_TO_REPORT: "Result recorded in report",
};

const TRACE_OBJECT_LABELS: Record<string, string> = {
  requirement: "Requirement",
  file: "Project file",
  memory: "Project memory",
  approval: "Approval",
  pem_snapshot: "Engineering model",
  analysis_result: "Analysis result",
  engineering_result: "Validated solver result",
  optimization_result: "Optimization result",
  external_model: "External solver model",
  integration_execution: "Solver integration run",
  cad_drawing: "CAD drawing",
  design_result: "Design result",
  report: "Report",
  user_request: "Engineer request",
  agent_execution: "Assistant activity",
  agent_result: "Assistant result",
};

export function getApprovalStatusLabel(status: string): string {
  return APPROVAL_STATUS_LABELS[status] ?? "Unknown status";
}

export function getMemoryTypeLabel(type: string): string {
  return MEMORY_TYPE_LABELS[type] ?? "Project note";
}

export function getLearningScopeLabel(scope: string): string {
  switch (scope) {
    case "PROJECT":
      return "Project";
    case "ENGINEER":
      return "Engineer";
    case "GLOBAL":
      return "Global";
    default:
      return scope;
  }
}

export function getLearningStatusLabel(status: string): string {
  switch (status) {
    case "CANDIDATE":
      return "Candidate";
    case "REVIEW":
      return "In review";
    case "APPROVED":
      return "Approved";
    case "REJECTED":
      return "Rejected";
    default:
      return status;
  }
}

export function getReportTypeLabel(type: string): string {
  return REPORT_TYPE_LABELS[type] ?? "Engineering report";
}

export function getReportStatusLabel(status: string): string {
  return REPORT_STATUS_LABELS[status] ?? status;
}

export function getFileStatusLabel(status: string): string {
  return FILE_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getTraceRelationshipLabel(type: string): string {
  return TRACE_RELATIONSHIP_LABELS[type] ?? "Related engineering step";
}

export function getTraceObjectLabel(type: string): string {
  return TRACE_OBJECT_LABELS[type] ?? "Engineering item";
}

export function getValidationStatusLabel(status: string): string {
  switch (status.toUpperCase()) {
    case "PASS":
    case "OK":
    case "SUCCESS":
      return "Checks passed";
    case "WARNING":
    case "WARN":
      return "Review recommended";
    case "ERROR":
    case "FAIL":
    case "FAILED":
      return "Issues found";
    default:
      return status.replaceAll("_", " ").toLowerCase();
  }
}

export function truncateText(text: string, max = 220): string {
  if (text.length <= max) {
    return text;
  }
  return `${text.slice(0, max).trim()}…`;
}
