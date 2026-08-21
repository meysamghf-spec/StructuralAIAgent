const ANALYSIS_STATUS_LABELS: Record<string, string> = {
  CREATED: "Queued",
  RUNNING: "Running",
  SUCCESS: "Completed",
  WARNING: "Completed with warnings",
  FAILED: "Failed",
  NOT_IMPLEMENTED: "Not available yet",
  REQUIRES_SOLVER: "Solver required",
  MODEL_NOT_READY: "Model not ready",
};

const CAPABILITY_STATUS_LABELS: Record<string, string> = {
  REQUIRES_SOLVER: "Connect ETABS, SAP2000, SAFE, or another solver to produce results",
  MODEL_NOT_READY: "Complete the engineering model before running analysis",
  NOT_IMPLEMENTED: "This analysis type is not supported yet",
  RUNNING: "Preparing analysis inputs",
};

export function getAnalysisStatusLabel(status: string): string {
  return ANALYSIS_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getAnalysisCapabilityLabel(status: string): string {
  return CAPABILITY_STATUS_LABELS[status] ?? getAnalysisStatusLabel(status);
}

export function formatAnalysisInventory(summary: Record<string, unknown>): string[] {
  const labels: Array<[string, string]> = [
    ["member_count", "Members"],
    ["support_count", "Supports"],
    ["load_case_count", "Load cases"],
    ["load_combination_count", "Load combinations"],
    ["level_count", "Levels"],
  ];
  return labels
    .filter(([key]) => typeof summary[key] === "number")
    .map(([key, label]) => `${label}: ${String(summary[key])}`);
}
