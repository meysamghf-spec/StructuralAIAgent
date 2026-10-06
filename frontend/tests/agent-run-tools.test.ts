import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  AGENT_RUN_SSE_EVENTS,
  applyAgentRunEvent,
  emptyAgentRun,
  mapToolExecution,
} from "../lib/agent-run-sse";
import { mapBackendMessage } from "../lib/chat-mappers";

function applyTool(run: ReturnType<typeof emptyAgentRun>, tool: Record<string, unknown>) {
  return applyAgentRunEvent(run, {
    type: AGENT_RUN_SSE_EVENTS.tool,
    data: { tool },
  });
}

describe("rich tool event mapping", () => {
  it("maps a rich document tool card", () => {
    const tool = mapToolExecution({
      id: "document_analysis",
      name: "Document Analysis",
      capability: "DOCUMENT_READ",
      status: "complete",
      operation: "DOCUMENT_SEARCHED",
      files: [{ filename: "plans.pdf", file_type: "PDF", availability: "indexed", page_count: 18 }],
      details: [
        { key: "file:plans.pdf", label: "plans.pdf", state: "complete" },
        { key: "pages:plans.pdf", label: "18 pages", state: "complete" },
        { key: "indexed:plans.pdf", label: "Indexed", state: "complete" },
        { key: "search:plans.pdf", label: "4 relevant sections found", state: "complete" },
      ],
      counts: { files: 1, relevant_sections: 4 },
      actions: [{ label: "View context", href: "/workspace/files" }],
    });
    expect(tool?.name).toBe("Document Analysis");
    expect(tool?.files?.[0]).toEqual({
      filename: "plans.pdf",
      fileType: "PDF",
      availability: "indexed",
      pageCount: 18,
    });
    expect(tool?.details).toHaveLength(4);
    expect(tool?.counts?.relevant_sections).toBe(4);
    expect(tool?.actions?.[0].label).toBe("View context");
  });

  it("aggregates multiple events for the same tool into one card", () => {
    let run = emptyAgentRun();
    run = applyTool(run, {
      id: "document_analysis",
      name: "Document Analysis",
      capability: "DOCUMENT_READ",
      status: "current",
      operation: "DOCUMENT_DISCOVERED",
      details: [{ key: "file:plans.pdf", label: "plans.pdf", state: "complete" }],
    });
    run = applyTool(run, {
      id: "document_analysis",
      name: "Document Analysis",
      capability: "DOCUMENT_READ",
      status: "current",
      operation: "DOCUMENT_INDEXED",
      details: [{ key: "indexed:plans.pdf", label: "Indexed", state: "complete" }],
    });
    run = applyTool(run, {
      id: "document_analysis",
      name: "Document Analysis",
      capability: "DOCUMENT_READ",
      status: "complete",
      operation: "DOCUMENT_SEARCHED",
      details: [{ key: "search:plans.pdf", label: "4 relevant sections found", state: "complete" }],
    });
    expect(run.tools).toHaveLength(1);
    expect(run.tools[0].status).toBe("complete");
    expect(run.tools[0].details.map((item) => item.label)).toEqual([
      "plans.pdf",
      "Indexed",
      "4 relevant sections found",
    ]);
  });

  it("renders a sparse tool event without requiring optional fields", () => {
    const tool = mapToolExecution({
      id: "capability_analysis_agent",
      name: "Structural Analysis",
      status: "current",
    });
    expect(tool?.details).toEqual([]);
    expect(tool?.files).toBeUndefined();
    expect(tool?.artifacts).toBeUndefined();
    expect(tool?.counts).toBeUndefined();
    expect(tool?.error).toBeUndefined();
  });

  it("maps engineering metadata and artifact references", () => {
    const mapped = mapBackendMessage({
      id: "m1",
      conversation_id: "c1",
      role: "assistant",
      content: "Analysis completed.",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "completed",
        agent_run: {
          lifecycle: "completed",
          current_step: "respond",
          tools: [
            {
              id: "capability_analysis_agent",
              name: "Structural Analysis",
              capability: "ANALYSIS_AGENT",
              status: "complete",
              details: [
                { label: "Model loaded", state: "complete" },
                { label: "42 members in model", state: "complete" },
                { label: "Validation: Pass", state: "complete" },
              ],
              counts: { members: 42, load_combinations: 8 },
              artifacts: [{ id: "art-1", name: "Lateral drift results", artifact_type: "analysis_result" }],
              actions: [{ label: "View analysis", href: "/workspace/analysis" }],
            },
          ],
          context: { conversation: true, project: true, files: [], indexed_document_count: 0 },
        },
      },
      created_at: "2026-01-01T00:00:00Z",
    });
    const tool = mapped.engineeringResult?.agentRun?.tools[0];
    expect(tool?.counts?.members).toBe(42);
    expect(tool?.artifacts?.[0]).toEqual({
      id: "art-1",
      name: "Lateral drift results",
      artifactType: "analysis_result",
    });
    expect(tool?.actions?.[0].href).toBe("/workspace/analysis");
  });

  it("maps a tool error state without crashing", () => {
    const tool = mapToolExecution({
      id: "capability_analysis_agent",
      name: "Structural Analysis",
      status: "error",
      details: [{ label: "Capability execution failed", state: "error" }],
      error: { title: "Tool execution failed", reason: "Unsupported ETABS version." },
    });
    expect(tool?.status).toBe("error");
    expect(tool?.error?.reason).toContain("Unsupported ETABS");
  });

  it("keeps a backwards-compatible basic tool event renderable", () => {
    let run = emptyAgentRun();
    run = applyTool(run, {
      id: "capability_analysis_agent",
      name: "Structural Analysis",
      capability: "ANALYSIS_AGENT",
      status: "current",
      details: [{ label: "Authorized tools: engineering.analysis.run", state: "complete" }],
    });
    expect(run.tools[0]).toMatchObject({
      id: "capability_analysis_agent",
      name: "Structural Analysis",
      status: "current",
    });
    expect(run.tools[0].details[0].label).toContain("engineering.analysis.run");
  });

  it("ignores malformed optional metadata instead of crashing", () => {
    const tool = mapToolExecution({
      id: "document_analysis",
      name: "Document Analysis",
      status: "complete",
      details: "not-an-array",
      files: [{ filename: "plans.pdf", page_count: "eighteen" }, "oops"],
      artifacts: null,
      counts: "nope",
      actions: [{ label: "Open", href: "https://evil.example" }],
      error: "boom",
      unexpected: { token: "abc" },
    });
    expect(tool?.details).toEqual([]);
    expect(tool?.files?.[0].pageCount).toBeNull();
    expect(tool?.artifacts).toBeUndefined();
    expect(tool?.counts).toBeUndefined();
    expect(tool?.actions).toBeUndefined();
    expect(tool?.error).toBeUndefined();
  });
});

describe("ToolExecutionCard source", () => {
  it("renders richer tool rows, artifacts, and actions without fake timers", () => {
    const source = readFileSync(resolve(__dirname, "../components/chat/ToolExecutionCard.tsx"), "utf8");
    expect(source).toContain("tool.details");
    expect(source).toContain("tool.files");
    expect(source).toContain("tool.artifacts");
    expect(source).toContain("tool.actions");
    expect(source).toContain("tool.error");
    expect(source).not.toContain("setTimeout");
    expect(source).not.toContain("setInterval");
  });
});
