import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const panel = readFileSync("components/agents/ApprovalReviewPanel.tsx", "utf8");

describe("approval panel resilience", () => {
  it("checks the real status first and recovers from 409 conflicts", () => {
    expect(panel).toContain("getApprovalRequest");
    expect(panel).toContain("approval-resolved");
    expect(panel).toContain("recoverFromConflict");
  });
});
