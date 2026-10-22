import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { mapBackendMessage } from "../lib/chat-mappers";
import { AGENT_CHAT_MODES } from "../lib/chat-types";

describe("agent run mapping", () => {
  it("maps structured agent_run metadata without inventing steps", () => {
    const mapped = mapBackendMessage({
      id: "m1",
      conversation_id: "c1",
      role: "assistant",
      content: "Analysis completed.",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "completed",
        selected_capability: "Analysis Agent",
        agent_run: {
          lifecycle: "completed",
          current_step: "respond",
          progress: "completed",
          selected_capability: "Analysis Agent",
          requires_approval: false,
          steps: [
            { key: "understand", label: "Understanding request", state: "complete" },
            { key: "execute", label: "Running structural analysis", state: "complete" },
            { key: "validate", label: "Validating results", state: "complete" },
            { key: "respond", label: "Final response", state: "complete" },
          ],
          tools: [
            {
              id: "capability_analysis_agent",
              name: "Structural Analysis",
              capability: "ANALYSIS_AGENT",
              status: "complete",
              details: [{ label: "Deterministic beam analysis completed", state: "complete" }],
            },
          ],
          context: {
            conversation: true,
            project: true,
            project_id: "p1",
            conversation_id: "c1",
            capability: "Analysis Agent",
            files: [{ filename: "plans.pdf", file_type: "PDF", availability: "indexed" }],
            indexed_document_count: 1,
          },
          validation_status: "PASS",
          error: null,
        },
      },
      created_at: "2026-01-01T00:00:00Z",
    });

    expect(mapped.engineeringResult?.agentRun?.lifecycle).toBe("completed");
    expect(mapped.engineeringResult?.agentRun?.steps).toHaveLength(4);
    expect(mapped.engineeringResult?.agentRun?.tools[0].name).toBe("Structural Analysis");
    expect(mapped.engineeringResult?.agentRun?.context.files[0].filename).toBe("plans.pdf");
    expect(mapped.engineeringResult?.demoResults).toBeNull();
  });

  it("maps failed agent_run errors without treating missing agent_run as progress", () => {
    const mapped = mapBackendMessage({
      id: "m2",
      conversation_id: "c1",
      role: "assistant",
      content: "Failed",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "failed",
        agent_run: {
          lifecycle: "failed",
          current_step: "execute",
          steps: [{ key: "execute", label: "Running structural analysis", state: "error" }],
          tools: [],
          context: { conversation: true, project: true, files: [], indexed_document_count: 0 },
          error: {
            title: "Engineering workflow failed",
            reason: "Unsupported ETABS version or corrupted file.",
          },
        },
      },
      created_at: "2026-01-01T00:00:00Z",
    });
    expect(mapped.engineeringResult?.agentRun?.error?.reason).toContain("Unsupported ETABS");
    expect(mapped.engineeringResult?.agentRun?.steps[0].state).toBe("error");
  });

  it("keeps approval metadata for in-chat review", () => {
    const mapped = mapBackendMessage({
      id: "m3",
      conversation_id: "c1",
      role: "assistant",
      content: "Approval required",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "awaiting_approval",
        requires_approval: true,
        approval_request_id: "apr-1",
        agent_run: {
          lifecycle: "waiting_for_approval",
          current_step: "approval",
          requires_approval: true,
          steps: [{ key: "approval", label: "Waiting for approval", state: "current" }],
          tools: [],
          context: { conversation: true, project: true, files: [] },
        },
      },
      created_at: "2026-01-01T00:00:00Z",
    });
    expect(mapped.engineeringResult?.requiresApproval).toBe(true);
    expect(mapped.engineeringResult?.approvalRequestId).toBe("apr-1");
    expect(mapped.engineeringResult?.agentRun?.steps[0].state).toBe("current");
  });
});

describe("agent run chat UI modules", () => {
  it("exports reusable progress, tool, context, and error components", async () => {
    const progress = await import("../components/chat/AgentProgress");
    const tool = await import("../components/chat/ToolExecutionCard");
    const context = await import("../components/chat/AgentContextStrip");
    const errorCard = await import("../components/chat/AgentErrorCard");
    expect(progress.AgentProgress).toBeTypeOf("function");
    expect(tool.ToolExecutionCard).toBeTypeOf("function");
    expect(context.AgentContextStrip).toBeTypeOf("function");
    expect(errorCard.AgentErrorCard).toBeTypeOf("function");
  });

  it("renders only supplied progress steps and supports reduced-motion CSS", () => {
    const progress = readFileSync(resolve(__dirname, "../components/chat/AgentProgress.tsx"), "utf8");
    const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf8");
    expect(progress).toContain("steps.map");
    expect(progress).not.toContain("setTimeout");
    expect(progress).not.toContain("setInterval");
    expect(css).toContain(".agent-progress");
    expect(css).toContain("prefers-reduced-motion");
  });

  it("ChatThread uses structured agent UI and keeps EngineeringResultCard", () => {
    const source = readFileSync(resolve(__dirname, "../components/chat/ChatThread.tsx"), "utf8");
    expect(source).toContain("AgentProgress");
    expect(source).toContain("ToolExecutionCard");
    expect(source).toContain("AgentContextStrip");
    expect(source).toContain("EngineeringResultCard");
    expect(source).toContain("AciRcBeamResultCard");
    expect(source).toContain("ApprovalReviewPanel");
    expect(source).toContain("liveProgressSteps");
    expect(source).not.toContain("setInterval");
  });

  it("composer exposes a lightweight Auto-default mode selector", () => {
    const source = readFileSync(resolve(__dirname, "../components/chat/ChatComposer.tsx"), "utf8");
    expect(source).toContain('aria-label="Agent mode"');
    expect(source).toContain("AGENT_CHAT_MODES");
    expect(AGENT_CHAT_MODES[0]).toEqual({ value: "auto", label: "Auto" });
    expect(AGENT_CHAT_MODES.map((item) => item.value)).toEqual([
      "auto",
      "analyze",
      "design",
      "cad",
      "documents",
      "reports",
    ]);
  });

  it("sidebar groups project, files, and capabilities without leaving chat-first navigation", () => {
    const source = readFileSync(resolve(__dirname, "../components/chat/ChatSidebar.tsx"), "utf8");
    expect(source).toContain("Project");
    expect(source).toContain("MainNav");
    expect(source).toContain("MainNav");
    expect(readFileSync(resolve(__dirname, "../lib/nav.ts"), "utf8")).toContain('href: "/workspace/files"');
    expect(readFileSync(resolve(__dirname, "../lib/nav.ts"), "utf8")).toContain('href: "/workspace/agents/builder"');
    expect(source).toContain("MainNav");
  });

  it("workspace opens the context panel only when requested or structured results exist", () => {
    const source = readFileSync(resolve(__dirname, "../components/chat/ChatWorkspace.tsx"), "utf8");
    expect(source).toContain("data-context-open");
    expect(source).toContain("hasStructuredContext");
    expect(source).toContain("setContextOpen(true)");
    expect(source).toContain("chat.mode");
  });

  it("useChat sends the selected mode through the existing chat API", () => {
    const source = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(source).toContain("mode: request.mode ?? mode");
    expect(source).toContain('useState<AgentChatMode>("auto")');
  });
});
