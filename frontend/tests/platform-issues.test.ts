import { describe, expect, it } from "vitest";
import { featureRequestLine, isFeatureRequest, sortIssues, type PlatformIssue } from "@/lib/platform-issues";

const mk = (id: string, status: string, severity: PlatformIssue["severity"], updated: string) =>
  ({ id, status, severity, updated_at: updated }) as PlatformIssue;

describe("sortIssues", () => {
  it("puts open before closed, then severity, then newest", () => {
    const sorted = sortIssues([
      mk("a", "resolved", "critical", "2026-01-03"),
      mk("b", "open", "low", "2026-01-01"),
      mk("c", "open", "high", "2026-01-02"),
      mk("d", "open", "high", "2026-01-05"),
    ]);
    expect(sorted.map((i) => i.id)).toEqual(["d", "c", "b", "a"]);
  });
});

describe("feature requests", () => {
  it("is detected by kind or category and summarised in one line", () => {
    const fr = {
      id: "f", kind: "feature_request", category: "feature_request", occurrences: 3,
      details: { capability_key: "pushover_analysis", estimate: { eta_en: "weeks (about 2-6 weeks)" }, request_count: 3 },
    } as unknown as PlatformIssue;
    expect(isFeatureRequest(fr)).toBe(true);
    expect(isFeatureRequest({ category: "feature_request" } as PlatformIssue)).toBe(true);
    expect(isFeatureRequest({ category: "bug", kind: "bug" } as PlatformIssue)).toBe(false);
    expect(featureRequestLine(fr)).toBe("pushover_analysis · weeks (about 2-6 weeks) · ×3");
    expect(featureRequestLine({ occurrences: 2 } as PlatformIssue)).toBe("×2");
  });
});
