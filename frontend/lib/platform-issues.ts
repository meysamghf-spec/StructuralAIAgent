import { apiFetch } from "./api";

export type PlatformIssue = {
  id: string;
  title: string;
  summary: string;
  category: string;
  severity: "low" | "medium" | "high" | "critical";
  source: string;
  status: string;
  page: string;
  conversation_id: string;
  project_id: string;
  user_message: string;
  assistant_excerpt: string;
  error_text: string;
  steps_to_reproduce: string;
  expected: string;
  actual: string;
  suspected_files: string[];
  occurrences: number;
  fix_note: string;
  fix_pr_url: string;
  proposed_fix: { kind?: string; title?: string; body?: string; diff?: string; status?: string; approved_by?: string } | null;
  created_at: string;
  updated_at: string;
  /** Optional (backend >= feature-request autoreport): "bug" | "feature_request". */
  kind?: string;
  details?: FeatureRequestDetails | Record<string, unknown>;
};

export type FeatureRequestDetails = {
  capability_key?: string;
  capability_title_en?: string;
  estimate?: { size?: string; eta_en?: string; eta_fa?: string; hours_min?: number; hours_max?: number; source?: string };
  closest_alternative?: { id?: string; text_en?: string };
  request_count?: number;
  sample_requests?: string[];
  project_context?: Record<string, unknown>;
};

export function isFeatureRequest(issue: Pick<PlatformIssue, "kind" | "category">): boolean {
  return issue.kind === "feature_request" || issue.category === "feature_request";
}

/** One-line summary for the admin list: "pushover_analysis · weeks (about 2-6 weeks) · ×3". */
export function featureRequestLine(issue: PlatformIssue): string {
  const d = (issue.details ?? {}) as FeatureRequestDetails;
  const parts = [d.capability_key, d.estimate?.eta_en, `×${d.request_count ?? issue.occurrences ?? 1}`];
  return parts.filter(Boolean).join(" · ");
}

export const ISSUE_STATUSES = [
  "open",
  "triaged",
  "fix_in_progress",
  "fix_ready",
  "awaiting_approval",
  "resolved",
  "rejected",
  "wontfix",
] as const;

export const OPEN_STATUSES = new Set(["open", "triaged", "fix_in_progress", "fix_ready", "awaiting_approval"]);

export function severityRank(severity: string): number {
  return { critical: 0, high: 1, medium: 2, low: 3 }[severity] ?? 4;
}

/** Open issues first, then by severity, then newest. */
export function sortIssues(items: PlatformIssue[]): PlatformIssue[] {
  return [...items].sort((a, b) => {
    const open = Number(OPEN_STATUSES.has(b.status)) - Number(OPEN_STATUSES.has(a.status));
    if (open) return open;
    const sev = severityRank(a.severity) - severityRank(b.severity);
    if (sev) return sev;
    return b.updated_at.localeCompare(a.updated_at);
  });
}

export async function checkPlatformAdmin(): Promise<boolean> {
  try {
    await apiFetch("/api/v1/platform-helper/admin-check");
    return true;
  } catch {
    return false;
  }
}

export async function listPlatformIssues(openOnly: boolean): Promise<PlatformIssue[]> {
  const r = await apiFetch<{ items: PlatformIssue[] }>(`/api/v1/admin/platform-issues?open_only=${openOnly}&limit=200`);
  return r.items;
}

export function postBackPlatformIssue(id: string, body: { status?: string; fix_note?: string; fix_pr_url?: string }) {
  return apiFetch<PlatformIssue>(`/api/v1/admin/platform-issues/${id}/post-back`, { method: "POST", body: JSON.stringify(body) });
}

export function proposeFix(id: string, body: { kind: "diff" | "pr_draft"; title: string; body: string; diff: string }) {
  return apiFetch<PlatformIssue>(`/api/v1/admin/platform-issues/${id}/propose-fix`, { method: "POST", body: JSON.stringify(body) });
}

export function approveFix(id: string) {
  return apiFetch<PlatformIssue>(`/api/v1/admin/platform-issues/${id}/approve-fix`, { method: "POST" });
}
