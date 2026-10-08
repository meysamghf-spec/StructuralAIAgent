import { describe, expect, it } from "vitest";
import {
  buildAssistantProfiles,
  getActiveProgressIndex,
  getProgressLabel,
  getValidationLabel,
  isTerminalProgress,
  approvedExperienceForExecution,
  learningProvenancePath,
  summarizeExecution,
} from "../lib/agent-workspace";
import type { AgentDefinitionSummary, AgentExecutionSummary } from "../lib/api";

describe("agent workspace helpers", () => {
  it("maps progress states to engineer-friendly labels", () => {
    expect(getProgressLabel("starting")).toBe("Received");
    expect(getProgressLabel("in_progress")).toBe("Processing");
    expect(getProgressLabel("awaiting_approval")).toBe("Review required");
    expect(getProgressLabel("completed")).toBe("Completed");
  });

  it("builds friendly assistant profiles without exposing agent enum names", () => {
    const agents: AgentDefinitionSummary[] = [
      {
        id: "agent-1",
        key: "analysis",
        name: "Analysis Agent",
        description: "Registered analysis assistant",
        agent_type: "ANALYSIS_AGENT",
        status: "ACTIVE",
        current_version: 1,
        configuration: {},
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ];

    const profiles = buildAssistantProfiles(agents);
    const analysis = profiles.find((profile) => profile.agentType === "ANALYSIS_AGENT");

    expect(analysis).toBeDefined();
    expect(analysis?.title).toBe("Structural Analysis Assistant");
    expect(analysis?.title).not.toContain("ANALYSIS_AGENT");
    expect(analysis?.capabilities.length).toBeGreaterThan(0);
    expect(analysis?.status).toBe("Available");
  });

  it("summarizes execution history for display", () => {
    const execution: AgentExecutionSummary = {
      id: "exec-1",
      project_id: "project-1",
      agent_definition_id: "agent-1",
      agent_version: 1,
      execution_status: "COMPLETED",
      approval_request_id: null,
      validation_status: "PASS",
      created_by: "engineer",
      created_at: "2026-01-01T12:00:00Z",
      updated_at: "2026-01-01T12:05:00Z",
      user_view: {
        progress: "completed",
        requires_approval: false,
        approval_request_id: null,
        final_result: "Completed successfully.",
        summary: "Validate the lateral system",
      },
      traceability_metadata: { report_id: "report-1" },
    };

    const summary = summarizeExecution(execution);
    expect(summary.title).toBe("Validate the lateral system");
    expect(summary.hasResult).toBe(true);
    expect(summary.reportAvailable).toBe(true);
  });

  it("detects approval requirement from user view", () => {
    const execution: AgentExecutionSummary = {
      id: "exec-2",
      project_id: "project-1",
      agent_definition_id: "agent-1",
      agent_version: 1,
      execution_status: "WAITING_APPROVAL",
      approval_request_id: "approval-1",
      validation_status: "REQUIRES_ENGINEER_REVIEW",
      created_by: "engineer",
      created_at: "2026-01-01T12:00:00Z",
      updated_at: "2026-01-01T12:05:00Z",
      user_view: {
        progress: "awaiting_approval",
        requires_approval: true,
        approval_request_id: "approval-1",
        final_result: "Awaiting engineer approval before results are finalized.",
        summary: "Update the structural model",
      },
    };

    expect(execution.user_view.requires_approval).toBe(true);
    expect(getProgressLabel(execution.user_view.progress)).toBe("Review required");
    expect(getValidationLabel(execution.validation_status)).toBe("Engineer review recommended");
    expect(getActiveProgressIndex("awaiting_approval")).toBe(2);
    expect(isTerminalProgress("completed")).toBe(true);
    expect(isTerminalProgress("awaiting_approval")).toBe(false);
  });

  it("labels completed results for final display", () => {
    const execution: AgentExecutionSummary = {
      id: "exec-3",
      project_id: "project-1",
      agent_definition_id: "agent-1",
      agent_version: 1,
      execution_status: "COMPLETED",
      approval_request_id: null,
      validation_status: "PASS",
      created_by: "engineer",
      created_at: "2026-01-01T12:00:00Z",
      updated_at: "2026-01-01T12:05:00Z",
      user_view: {
        progress: "completed",
        requires_approval: false,
        approval_request_id: null,
        final_result: "Stub handler completed.",
        summary: "Generate project summary",
      },
    };

    const summary = summarizeExecution(execution);
    expect(summary.hasResult).toBe(true);
    expect(getProgressLabel(execution.user_view.progress)).toBe("Completed");
  });

  it("reads approved experience as context only and links to provenance", () => {
    const execution: AgentExecutionSummary = {
      id: "exec-4",
      project_id: "project-1",
      agent_definition_id: "agent-1",
      agent_version: 1,
      execution_status: "COMPLETED",
      approval_request_id: null,
      validation_status: "NOT_RUN",
      created_by: "engineer",
      created_at: "2026-01-01T12:00:00Z",
      updated_at: "2026-01-01T12:05:00Z",
      user_view: {
        progress: "completed",
        requires_approval: false,
        approval_request_id: null,
        final_result: "Connect an analysis solver adapter before treating results as engineering conclusions.",
        summary: "Analyze the lateral system",
      },
      traceability_metadata: {
        approved_engineering_experience: {
          heading: "APPROVED ENGINEERING EXPERIENCE — CONTEXT ONLY",
          authority: "CONTEXT_ONLY",
          records: [
            {
              id: "learning-1",
              learning_scope: "PROJECT",
              applicability: { analysis_type: "LATERAL_DRIFT" },
              explanation: "Call out diaphragm confirmation.",
              authority: "CONTEXT_ONLY",
            },
          ],
        },
      },
    };

    const experience = approvedExperienceForExecution(execution);
    expect(experience?.heading).toBe("APPROVED ENGINEERING EXPERIENCE — CONTEXT ONLY");
    expect(experience?.authority).toBe("CONTEXT_ONLY");
    expect(experience?.records[0]?.id).toBe("learning-1");
    expect(learningProvenancePath("project-1", "learning-1")).toBe(
      "/workspace/learning?project=project-1&record=learning-1",
    );
    expect(approvedExperienceForExecution({ traceability_metadata: {} })).toBeNull();
  });
});
