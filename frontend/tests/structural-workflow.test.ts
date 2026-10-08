import { describe, expect, it } from "vitest";
import type { AgentExecutionSummary } from "../lib/api";
import {
  buildEngineeringBriefPayload,
  emptyEngineeringBrief,
  structuralWorkflowGlance,
} from "../lib/structural-workflow";

function execution(workflow: Record<string, unknown> | undefined): AgentExecutionSummary {
  return {
    id: "run-1",
    project_id: "project-1",
    agent_definition_id: "agent-1",
    agent_version: 1,
    execution_status: "COMPLETED",
    approval_request_id: null,
    validation_status: "NOT_RUN",
    created_by: "engineer",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    user_view: {
      progress: "completed",
      requires_approval: false,
      approval_request_id: null,
      final_result: "Analysis cannot start",
      summary: "Validate the model",
    },
    output: workflow ? { structural_workflow: workflow } : {},
  };
}

describe("structural workflow glance", () => {
  it("reads model, analysis, design, QA, and output from the run", () => {
    const glance = structuralWorkflowGlance(
      execution({
        model_readiness: { status: "READY" },
        analysis: { status: "SUCCESS", executed: true },
        design_checks: [{ status: "PASS", recognized: true }],
        qa: { status: "PASS" },
        engineering_report: { title: "Report" },
        final_engineering_approval: false,
        engineer_message: "Completed beam checks passed.",
      }),
    );
    expect(glance).toMatchObject({
      model: "READY",
      analysis: "SUCCESS",
      design: "PASS",
      qa: "PASS",
      output: "Available",
      approval: "Not approved",
    });
  });

  it("does not treat a missing calculation as a design pass", () => {
    const glance = structuralWorkflowGlance(
      execution({
        model_readiness: { status: "NOT_READY" },
        analysis: { status: "NOT_RUN", executed: false },
        design_checks: [],
        qa: { status: "NOT_RUN" },
        engineer_message: "Analysis cannot start because support conditions are missing.",
      }),
    );
    expect(glance?.design).toBe("NOT_RUN");
    expect(glance?.qa).toBe("NOT_RUN");
    expect(glance?.output).toBe("Not generated");
  });
});

describe("engineering brief payload", () => {
  it("sends each field with provenance and leaves blanks unavailable", () => {
    const fields = emptyEngineeringBrief();
    fields.project_type = { value: "residential", origin: "USER_PROVIDED" };
    fields.story_heights = { value: "3, 3, 3", origin: "ASSUMED" };
    fields.loads = { value: "   ", origin: "CALCULATED" };
    const payload = buildEngineeringBriefPayload(fields);
    expect(payload.project_type).toEqual({ value: "residential", origin: "USER_PROVIDED" });
    expect(payload.story_heights).toEqual({ value: "3, 3, 3", origin: "ASSUMED" });
    expect(payload.loads).toEqual({ value: null, origin: "UNAVAILABLE" });
    expect(payload.design_code.origin).toBe("UNAVAILABLE");
    expect(Object.keys(payload)).toContain("seismic_assumptions");
    expect(Object.keys(payload)).toContain("wind_assumptions");
  });
});
