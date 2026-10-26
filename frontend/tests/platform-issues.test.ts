import { describe, expect, it } from "vitest";
import { sortIssues, type PlatformIssue } from "@/lib/platform-issues";

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
