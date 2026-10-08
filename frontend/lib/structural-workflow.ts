import type { AgentExecutionSummary } from "./api";

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
