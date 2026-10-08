import type { AgentExecutionSummary } from "./api";

export const BRIEF_ORIGINS = [
  "USER_PROVIDED",
  "ASSUMED",
  "DERIVED",
  "CALCULATED",
  "UNAVAILABLE",
] as const;

export type BriefOrigin = (typeof BRIEF_ORIGINS)[number];

export type BriefFieldState = {
  value: string;
  origin: BriefOrigin;
};

export const ENGINEERING_BRIEF_FIELDS = [
  { key: "project_type", label: "Project type" },
  { key: "location", label: "Location" },
  { key: "plot_length_m", label: "Plot length (m)" },
  { key: "plot_width_m", label: "Plot width (m)" },
  { key: "frontage_m", label: "Frontage (m)" },
  { key: "number_of_stories", label: "Number of stories" },
  { key: "story_heights", label: "Story heights" },
  { key: "grid", label: "Grid" },
  { key: "spans", label: "Spans" },
  { key: "structural_system", label: "Structural system" },
  { key: "material", label: "Material" },
  { key: "member_assumptions", label: "Member assumptions" },
  { key: "loads", label: "Loads" },
  { key: "design_code", label: "Design code" },
  { key: "units", label: "Units" },
  { key: "foundation_assumptions", label: "Foundation assumptions" },
  { key: "seismic_assumptions", label: "Seismic assumptions" },
  { key: "wind_assumptions", label: "Wind assumptions" },
  { key: "engineer_notes", label: "Engineer notes" },
] as const;

export type EngineeringBriefFieldKey = (typeof ENGINEERING_BRIEF_FIELDS)[number]["key"];

export function emptyEngineeringBrief(): Record<EngineeringBriefFieldKey, BriefFieldState> {
  return Object.fromEntries(
    ENGINEERING_BRIEF_FIELDS.map((field) => [field.key, { value: "", origin: "UNAVAILABLE" as const }]),
  ) as Record<EngineeringBriefFieldKey, BriefFieldState>;
}

export function buildEngineeringBriefPayload(
  fields: Record<string, BriefFieldState>,
): Record<string, { value: string | null; origin: BriefOrigin }> {
  const payload: Record<string, { value: string | null; origin: BriefOrigin }> = {};
  for (const field of ENGINEERING_BRIEF_FIELDS) {
    const current = fields[field.key] ?? { value: "", origin: "UNAVAILABLE" as const };
    const value = current.value.trim();
    payload[field.key] = {
      value: value ? value : null,
      origin: value ? current.origin : "UNAVAILABLE",
    };
  }
  return payload;
}

export type WorkflowGlance = {
  model: string;
  analysis: string;
  design: string;
  qa: string;
  output: string;
  message: string | null;
  approval: string;
};

type WorkflowPackage = {
  model_readiness?: { status?: string };
  analysis?: { status?: string; executed?: boolean };
  design_checks?: Array<{ status?: string; recognized?: boolean }>;
  qa?: { status?: string };
  engineering_report?: unknown;
  final_engineering_approval?: boolean;
  engineer_message?: string;
};

export function structuralWorkflowGlance(
  execution: AgentExecutionSummary | null | undefined,
): WorkflowGlance | null {
  const workflow = execution?.output?.structural_workflow;
  if (!workflow || typeof workflow !== "object") {
    return null;
  }
  const packageData = workflow as WorkflowPackage;
  const recognized = (packageData.design_checks ?? []).filter((item) => item.recognized);
  const designStatus = recognized.some((item) => item.status === "FAIL")
    ? "FAIL"
    : recognized.some((item) => item.status === "PASS")
      ? "PASS"
      : "NOT_RUN";
  return {
    model: packageData.model_readiness?.status ?? "NOT_RUN",
    analysis: packageData.analysis?.executed
      ? packageData.analysis.status ?? "SUCCESS"
      : packageData.analysis?.status ?? "NOT_RUN",
    design: designStatus,
    qa: packageData.qa?.status ?? "NOT_RUN",
    output: packageData.engineering_report ? "Available" : "Not generated",
    message: packageData.engineer_message ?? null,
    approval: packageData.final_engineering_approval ? "Approved" : "Not approved",
  };
}
