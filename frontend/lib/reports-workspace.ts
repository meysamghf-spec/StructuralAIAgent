import type { ReportSummary } from "./api";

/** Report type shown for the calculation report built from the latest 3D frame run. */
export const FRAME_REPORT_ID = "frame3d-calculation-report";

export type ReportRow = {
  id: string;
  /** "stored" = a report record from /api/v1/reports; "frame3d" = the calculation report of the latest frame run. */
  source: "stored" | "frame3d";
  title: string;
  /** Raw backend type (STRUCTURAL_DESIGN, ANALYSIS …) or "CALCULATION". */
  type: string;
  status: string | null;
  version: number | null;
  date: string | null;
};

export const REPORT_GENERATE_TYPES = [
  "PROJECT_SUMMARY",
  "STRUCTURAL_DESIGN",
  "ANALYSIS",
  "VALIDATION",
  "DECISION_HISTORY",
] as const;

const TYPE_KEY: Record<string, string> = {
  STRUCTURAL_DESIGN: "Structural design report",
  ANALYSIS: "Analysis report",
  VALIDATION: "Validation report",
  PROJECT_SUMMARY: "Project summary",
  DECISION_HISTORY: "Decision history",
  CALCULATION: "Calculation report",
};

const STATUS_KEY: Record<string, string> = {
  DRAFT: "Draft",
  GENERATING: "Generating",
  COMPLETED: "Ready",
  FAILED: "Failed",
};

/** i18n key for a report type (translate with the UI `t`). */
export function reportTypeKey(type: string): string {
  return TYPE_KEY[type] ?? "Engineering report";
}

/** i18n key for a report status; unknown statuses come back unchanged. */
export function reportStatusKey(status: string): string {
  return STATUS_KEY[status] ?? status;
}

/** Rows for the list, newest first. Never throws on a malformed API body; never invents data. */
export function buildReportRows(reports: unknown, frameReportAvailable: boolean): ReportRow[] {
  const rows: ReportRow[] = [];
  const list = Array.isArray(reports) ? (reports as ReportSummary[]) : [];
  for (const r of list) {
    if (!r || typeof r !== "object" || !r.id) continue;
    rows.push({
      id: r.id,
      source: "stored",
      title: r.title || "",
      type: r.report_type,
      status: r.status ?? null,
      version: typeof r.current_version === "number" ? r.current_version : null,
      date: r.updated_at ?? r.created_at ?? null,
    });
  }
  rows.sort((a, b) => Date.parse(b.date ?? "") - Date.parse(a.date ?? "") || 0);
  if (frameReportAvailable) {
    rows.unshift({
      id: FRAME_REPORT_ID,
      source: "frame3d",
      title: "Calculation report",
      type: "CALCULATION",
      status: null,
      version: null,
      date: null,
    });
  }
  return rows;
}

export type VersionSection = { key: string; title: string; text: string; missing: boolean };

/** Sections of a generated report version (content.sections), for the inline viewer. */
export function versionSections(content: unknown): VersionSection[] {
  const raw = (content as { sections?: unknown } | null | undefined)?.sections;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((s): s is Record<string, unknown> => Boolean(s) && typeof s === "object")
    .map((s, i) => {
      const body = s.content;
      return {
        key: typeof s.key === "string" ? s.key : String(i),
        title: typeof s.title === "string" && s.title ? s.title : typeof s.key === "string" ? s.key : `#${i + 1}`,
        text: body && typeof body === "object" && Object.keys(body).length ? JSON.stringify(body, null, 2) : "",
        missing: sectionMissing(body),
      };
    });
}

const MISSING_STATUS = new Set(["unavailable", "not_run", "not_generated", "missing"]);

function sectionMissing(body: unknown): boolean {
  const a = (body as { data_availability?: { status?: unknown } } | null | undefined)?.data_availability;
  return typeof a?.status === "string" && MISSING_STATUS.has(a.status);
}

export function versionMissingData(traceability: unknown): string[] {
  const m = (traceability as { missing_data?: unknown } | null | undefined)?.missing_data;
  return Array.isArray(m) ? m.filter((x): x is string => typeof x === "string") : [];
}

export function reportJsonFilename(title: string, type: string, version: number | null): string {
  const base = (title || type || "report").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || type.toLowerCase();
  return `${base}${version ? `-v${version}` : ""}.json`;
}
