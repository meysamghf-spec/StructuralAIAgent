const DESIGN_STATUS_LABELS: Record<string, string> = {
  CREATED: "Queued",
  RUNNING: "Running",
  PASS: "Checks passed",
  FAIL: "Checks failed",
  WARNING: "Review recommended",
  NOT_IMPLEMENTED: "Not available yet",
  REQUIRES_SOLVER: "Design engine required",
  REQUIRES_ANALYSIS: "Analysis results required",
  MODEL_NOT_READY: "Model not ready",
  REQUIRES_ENGINEER_REVIEW: "Engineer review required",
};

const DESIGN_CAPABILITY_LABELS: Record<string, string> = {
  REQUIRES_SOLVER:
    "Real design calculations require a connected deterministic design engine or external solver.",
  REQUIRES_ANALYSIS:
    "Complete structural analysis with engineering outputs before running code-based design checks.",
  MODEL_NOT_READY: "Complete the engineering model before starting design.",
  NOT_IMPLEMENTED: "This design type is not supported yet.",
  REQUIRES_ENGINEER_REVIEW: "Review the active code configuration before proceeding.",
};

const DESIGN_CAPABILITY_LABELS_FA: Record<string, string> = {
  REQUIRES_SOLVER:
    "برای انجام محاسبات واقعی طراحی، یک موتور تحلیل/طراحی معتبر باید متصل باشد.",
  REQUIRES_ANALYSIS:
    "قبل از طراحی، باید نتایج مهندسی تحلیل سازه با خروجی‌های واقعی آماده شود.",
  MODEL_NOT_READY: "مدل مهندسی باید قبل از طراحی تکمیل شود.",
};

export function getDesignStatusLabel(status: string): string {
  return DESIGN_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getDesignCapabilityLabel(status: string, locale: "en" | "fa" = "en"): string {
  if (locale === "fa" && DESIGN_CAPABILITY_LABELS_FA[status]) {
    return DESIGN_CAPABILITY_LABELS_FA[status];
  }
  return DESIGN_CAPABILITY_LABELS[status] ?? getDesignStatusLabel(status);
}

export function formatDesignInventory(summary: Record<string, unknown>): string[] {
  const labels: Array<[string, string]> = [
    ["member_count", "Members"],
    ["material_count", "Materials"],
    ["section_count", "Sections"],
    ["load_combination_count", "Load combinations"],
  ];
  return labels
    .filter(([key]) => typeof summary[key] === "number")
    .map(([key, label]) => `${label}: ${String(summary[key])}`);
}
