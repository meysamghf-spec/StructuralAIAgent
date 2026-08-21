import { describe, expect, it } from "vitest";
import {
  getApprovalStatusLabel,
  getMemoryTypeLabel,
  getReportTypeLabel,
  getTraceObjectLabel,
  getTraceRelationshipLabel,
  getValidationStatusLabel,
  truncateText,
} from "../lib/workspace";
import { getProgressLabel as getAgentProgressLabel } from "../lib/agent-workspace";

describe("workspace display helpers", () => {
  it("maps approval statuses to friendly labels", () => {
    expect(getApprovalStatusLabel("PENDING")).toBe("Awaiting review");
    expect(getApprovalStatusLabel("APPROVED")).toBe("Approved");
  });

  it("maps memory and report types to friendly labels", () => {
    expect(getMemoryTypeLabel("DECISION")).toBe("Decision");
    expect(getReportTypeLabel("PROJECT_SUMMARY")).toBe("Project summary");
  });

  it("maps traceability labels for engineer-readable chain view", () => {
    expect(getTraceObjectLabel("agent_execution")).toBe("Assistant activity");
    expect(getTraceRelationshipLabel("REQUEST_TO_AGENT_EXECUTION")).toBe(
      "Request started assistant work",
    );
  });

  it("maps validation statuses consistently", () => {
    expect(getValidationStatusLabel("PASS")).toBe("Checks passed");
    expect(getValidationStatusLabel("WARNING")).toBe("Review recommended");
  });

  it("truncates long text for cards", () => {
    expect(truncateText("short")).toBe("short");
    expect(truncateText("x".repeat(300)).endsWith("…")).toBe(true);
  });

  it("keeps agent progress labels engineer-friendly", () => {
    expect(getAgentProgressLabel("awaiting_approval")).toBe("Review required");
    expect(getAgentProgressLabel("completed")).toBe("Completed");
  });
});

describe("loading agents and executions expectations", () => {
  it("defines user-facing progress states", () => {
    const states = [
      "starting",
      "in_progress",
      "awaiting_approval",
      "completed",
      "rejected",
      "failed",
    ] as const;

    for (const state of states) {
      expect(getAgentProgressLabel(state)).not.toContain("_");
      expect(getAgentProgressLabel(state)).not.toContain("AGENT");
    }
  });

  it("shows approval requirement in progress language", () => {
    expect(getAgentProgressLabel("awaiting_approval")).toContain("Review");
  });

  it("shows completed result language", () => {
    expect(getAgentProgressLabel("completed")).toBe("Completed");
  });
});
