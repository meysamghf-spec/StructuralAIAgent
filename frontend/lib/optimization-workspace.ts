const OPTIMIZATION_STATUS_LABELS: Record<string, string> = {
  CREATED: "Queued",
  RUNNING: "Running",
  PASS: "Optimization complete",
  FAIL: "Optimization failed",
  WARNING: "Review recommended",
  NOT_IMPLEMENTED: "Not available yet",
  REQUIRES_SOLVER: "Optimization engine required",
  REQUIRES_ANALYSIS: "Analysis results required",
  REQUIRES_DESIGN: "Design results required",
  MODEL_NOT_READY: "Model not ready",
  REQUIRES_ENGINEER_REVIEW: "Engineer review required",
};

const OPTIMIZATION_CAPABILITY_LABELS: Record<string, string> = {
  REQUIRES_SOLVER:
    "Real structural optimization requires a connected deterministic optimization engine or external solver.",
  REQUIRES_ANALYSIS:
    "Complete structural analysis with engineering outputs before running optimization.",
  REQUIRES_DESIGN:
    "Complete code-based design with engineering outputs before running optimization.",
  MODEL_NOT_READY: "Complete the engineering model before starting optimization.",
  NOT_IMPLEMENTED: "This optimization objective is not supported yet.",
  REQUIRES_ENGINEER_REVIEW: "Review the active code configuration before proceeding.",
};

const OPTIMIZATION_CAPABILITY_LABELS_FA: Record<string, string> = {
  REQUIRES_SOLVER:
    "بهینه‌سازی با موتور کامل SAIA (تحلیل سه‌بعدی، طراحی مبحث ۹ و کنترل دریفت ۲۸۰۰) روی مدل این پروژه اجرا می‌شود.",
  REQUIRES_ANALYSIS:
    "قبل از بهینه‌سازی، باید نتایج مهندسی تحلیل سازه با خروجی‌های واقعی آماده شود.",
  REQUIRES_DESIGN:
    "قبل از بهینه‌سازی، باید نتایج مهندسی طراحی با خروجی‌های واقعی آماده شود.",
  MODEL_NOT_READY: "مدل مهندسی باید قبل از بهینه‌سازی تکمیل شود.",
};

export function getOptimizationStatusLabel(status: string): string {
  return OPTIMIZATION_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getOptimizationCapabilityLabel(
  status: string,
  locale: "en" | "fa" = "en",
): string {
  if (locale === "fa" && OPTIMIZATION_CAPABILITY_LABELS_FA[status]) {
    return OPTIMIZATION_CAPABILITY_LABELS_FA[status];
  }
  return OPTIMIZATION_CAPABILITY_LABELS[status] ?? getOptimizationStatusLabel(status);
}

export function formatOptimizationInventory(summary: Record<string, unknown>): string[] {
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

export type OptimizationMemberResult = {
  member_id?: string;
  member_name?: string;
  member_type?: string;
  selected_section_id?: string;
  selected_section_name?: string;
  governing_utilization?: number;
  status?: string;
  message?: string;
};

export type OptimizationSharedGroup = {
  member_ids?: string[];
  member_names?: string[];
  selected_section_id?: string;
  selected_section_name?: string;
  governing_utilization?: number;
};

export function formatOptimizationMode(mode: string | undefined): string {
  if (mode === "SHARED_SECTION") return "Shared section for group";
  if (mode === "INDEPENDENT") return "Independent per member";
  return "Standard optimization";
}

export function formatMemberOptimizationResults(outputs: Record<string, unknown>): string[] {
  const memberResults = outputs.member_results;
  if (!Array.isArray(memberResults)) {
    return [];
  }
  return memberResults
    .map((item) => {
      if (typeof item !== "object" || item === null) return "";
      const record = item as OptimizationMemberResult;
      if (!record.member_name) return "";
      if (record.selected_section_name) {
        const utilization =
          typeof record.governing_utilization === "number"
            ? ` · utilization ${record.governing_utilization}`
            : "";
        return `${record.member_name}: ${record.selected_section_name}${utilization}`;
      }
      return `${record.member_name}: no valid section selected`;
    })
    .filter(Boolean);
}

export function formatSharedSectionGroups(outputs: Record<string, unknown>): string[] {
  const groups = outputs.shared_section_groups;
  if (!Array.isArray(groups) || groups.length === 0) {
    return [];
  }
  return groups
    .map((item) => {
      if (typeof item !== "object" || item === null) return "";
      const record = item as OptimizationSharedGroup;
      const names = (record.member_names ?? []).join(", ");
      if (!record.selected_section_name) return "";
      return `Shared ${record.selected_section_name} for ${names}`;
    })
    .filter(Boolean);
}

/** Persian message + readiness steps when the project has no model the optimizer can use. */
export const NO_MODEL_MESSAGE_FA =
  "این پروژه هنوز مدل سازه ندارد؛ ابتدا مدل را بسازید یا وارد کنید، سپس بهینه‌سازی را شروع کنید.";
export const NO_MODEL_STEPS_FA = [
  "در چت قاب را توصیف کنید (مثلاً «قاب ۴ طبقه با ۳×۳ دهانه ۵ متری، پهنه خطر زیاد، خاک نوع ۲») یا «پیش‌فرض‌ها را فرض کن» را بزنید.",
  "یا فایل ETABS / SAP / DXF را از بخش ورود مدل وارد و بازبینی مهندس را تأیید کنید.",
  "بارها و ترکیب‌بارهای مبحث ۶ / ۲۸۰۰ و کاتالوگ استاندارد مقاطع به‌صورت خودکار اعمال می‌شوند (فهرست مقاطع اختیاری است).",
  "سپس دوباره «Start optimization» را بزنید؛ تحلیل و طراحی داخل حلقه بهینه‌سازی انجام می‌شود.",
];
