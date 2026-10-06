import { describe, expect, it } from "vitest";

import {
  AGENT_RUN_SSE_EVENTS,
  applyAgentRunEvent,
  emptyAgentRun,
  isTerminalAgentRunEvent,
  parseSseBlock,
} from "../lib/agent-run-sse";

describe("agent-run SSE parsing", () => {
  it("parses a valid event block", () => {
    const event = parseSseBlock(
      'event: agent_run.step\ndata: {"step_id":"execute","name":"Running engineering workflow","status":"current"}',
    );
    expect(event).toEqual({
      type: AGENT_RUN_SSE_EVENTS.step,
      data: {
        step_id: "execute",
        name: "Running engineering workflow",
        status: "current",
      },
    });
  });

  it("returns null for malformed JSON or missing fields", () => {
    expect(parseSseBlock("event: agent_run.step\ndata: {nope")).toBeNull();
    expect(parseSseBlock("data: {\"step_id\":\"execute\"}")).toBeNull();
    expect(parseSseBlock("")).toBeNull();
  });
});

describe("agent-run SSE state updates", () => {
  it("updates progress, tools, context, approval, completion, and failure", () => {
    let run = emptyAgentRun();
    run = applyAgentRunEvent(run, {
      type: AGENT_RUN_SSE_EVENTS.step,
      data: { step_id: "understand", name: "Understanding request", status: "current" },
    });
    expect(run.steps[0]).toEqual({
      key: "understand",
      label: "Understanding request",
      state: "current",
    });
    run = applyAgentRunEvent(run, {
      type: AGENT_RUN_SSE_EVENTS.step,
      data: { step_id: "understand", name: "Understanding request", status: "complete" },
    });
    expect(run.steps[0].state).toBe("complete");
    run = applyAgentRunEvent(run, {
      type: AGENT_RUN_SSE_EVENTS.tool,
      data: {
        tool: {
          id: "capability_analysis_agent",
          name: "Structural Analysis",
          capability: "ANALYSIS_AGENT",
          status: "current",
          details: [{ label: "Authorized tools: engineering.analysis.run", state: "complete" }],
        },
      },
    });
    expect(run.tools[0].name).toBe("Structural Analysis");
    run = applyAgentRunEvent(run, {
      type: AGENT_RUN_SSE_EVENTS.context,
      data: { context: { conversation: true, project: true, project_id: "p1" } },
    });
    expect(run.context.project).toBe(true);
    run = applyAgentRunEvent(run, {
      type: AGENT_RUN_SSE_EVENTS.approvalRequired,
      data: { approval_request_id: "apr-1" },
    });
    expect(run.requiresApproval).toBe(true);
    expect(run.lifecycle).toBe("waiting_for_approval");
    run = applyAgentRunEvent(run, {
      type: AGENT_RUN_SSE_EVENTS.completed,
      data: { assistant_message: { id: "a1" } },
    });
    expect(run.lifecycle).toBe("completed");
    const failed = applyAgentRunEvent(emptyAgentRun(), {
      type: AGENT_RUN_SSE_EVENTS.failed,
      data: { error: { title: "Engineering workflow failed", reason: "Unsupported ETABS version." } },
    });
    expect(failed.error?.reason).toContain("Unsupported ETABS");
  });

  it("treats only terminal events that include the assistant message as complete", () => {
    expect(isTerminalAgentRunEvent(AGENT_RUN_SSE_EVENTS.approvalRequired, {})).toBe(false);
    expect(
      isTerminalAgentRunEvent(AGENT_RUN_SSE_EVENTS.completed, { assistant_message: { id: "a1" } }),
    ).toBe(true);
    expect(isTerminalAgentRunEvent(AGENT_RUN_SSE_EVENTS.step, { assistant_message: { id: "a1" } })).toBe(
      false,
    );
  });

  it("ignores unknown event types", () => {
    const run = emptyAgentRun({ lifecycle: "executing" });
    expect(applyAgentRunEvent(run, { type: "agent_run.unknown", data: { step_id: "x" } }).lifecycle).toBe(
      "executing",
    );
  });
});
