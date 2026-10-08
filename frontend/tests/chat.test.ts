import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

import {

  attachmentLimitationNote,

  attachmentStatusLabel,

  buildOptimisticUserMessage,

  buildSendPayload,

  canSendMessage,

  createOptimisticMessageId,

  extractChatActions,

  filterConversations,

  formatChatError,

  handleComposerKeyDown,

  isOptimisticMessage,

  parseMessageContent,

  renderInlineMarkdown,

  replaceOptimisticMessages,

  shouldShowEngineeringDisclaimer,

  shouldShowProminentPrompt,

  pendingChatApprovalId,

  workspaceActionsForChat,

} from "../lib/chat";

import { mapBackendMessage } from "../lib/chat-mappers";

import { ENGINEERING_PROMPT_EXAMPLES, STREAMING_CAPABILITIES } from "../lib/chat-types";

import type { ChatMessage } from "../lib/chat-api";



describe("chat helpers", () => {

  it("allows send when text or ready attachments exist", () => {

    expect(canSendMessage("Analyze model", [])).toBe(true);

    expect(

      canSendMessage("", [

        {

          localId: "1",

          file: new File(["x"], "a.pdf"),

          uploaded: {

            file_id: "f1",

            filename: "a.pdf",

            file_type: "PDF",

            content_type: "application/pdf",

            status: "ready",

            parsing_status: "COMPLETE",

            extraction_status: "COMPLETE",

          },

        },

      ]),

    ).toBe(true);

    expect(

      canSendMessage("", [{ localId: "1", file: new File(["x"], "a.pdf"), uploading: true }]),

    ).toBe(false);

  });



  it("builds unified send payload with attachment ids", () => {

    const payload = buildSendPayload("Check drift", [

      {

        localId: "1",

        file: new File(["x"], "model.edb"),

        uploaded: {

          file_id: "file-1",

          filename: "model.edb",

          file_type: "UNKNOWN",

          content_type: null,

          status: "ready",

          parsing_status: "SKIPPED",

          extraction_status: "SKIPPED",

        },

      },

    ]);

    expect(payload.content).toBe("Check drift");

    expect(payload.attachment_file_ids).toEqual(["file-1"]);

  });



  it("Enter sends and Shift+Enter does not", () => {

    const onSend = vi.fn();

    handleComposerKeyDown(

      { key: "Enter", shiftKey: false, preventDefault: vi.fn() },

      onSend,

    );

    expect(onSend).toHaveBeenCalledTimes(1);



    onSend.mockClear();

    handleComposerKeyDown(

      { key: "Enter", shiftKey: true, preventDefault: vi.fn() },

      onSend,

    );

    expect(onSend).not.toHaveBeenCalled();

  });



  it("formats chat errors without internal details", () => {

    expect(formatChatError(new Error("Failed to fetch"))).toContain("temporarily unavailable");

    expect(formatChatError(new Error("Traceback (most recent call last)"))).toBe(

      "Something went wrong. Please try again.",

    );
    expect(formatChatError(new Error("Request failed (403)"))).toContain("do not have access");
    expect(formatChatError(new Error("Request failed (404)"))).toContain("not found");
    expect(formatChatError(new Error("Request failed (422)"))).toContain("could not be processed");
    expect(formatChatError(new Error("Request failed (500)"))).toContain("encountered an error");

  });



  it("filters conversations by title", () => {

    const conversations = [

      { id: "1", title: "Bridge analysis" },

      { id: "2", title: "Tower drift review" },

    ];

    expect(filterConversations(conversations, "bridge")).toEqual([conversations[0]]);

    expect(filterConversations(conversations, "")).toEqual(conversations);

  });



  it("parses headings, list items, and paragraphs", () => {

    const blocks = parseMessageContent("### Result\n- Item one\nPlain text");

    expect(blocks[0]).toEqual({ type: "heading", text: "Result" });

    expect(blocks[1]).toEqual({ type: "list-item", text: "Item one" });

    expect(blocks[2]).toEqual({ type: "paragraph", text: "Plain text" });

  });



  it("renders inline bold markdown segments", () => {

    expect(renderInlineMarkdown("**Status:** complete")).toEqual([

      { bold: "Status:" },

      " complete",

    ]);

  });



  it("reports attachment extraction limitations honestly", () => {
    expect(
      attachmentLimitationNote({
        file_id: "f1",
        filename: "specification.pdf",
        file_type: "PDF",
        content_type: "application/pdf",
        status: "ready",
        parsing_status: "SKIPPED",
        extraction_status: "SKIPPED",
      }),
    ).toContain("not automatically parsed");

    expect(
      attachmentLimitationNote({
        file_id: "f2",
        filename: "tower.dwg",
        file_type: "UNKNOWN",
        content_type: null,
        status: "ready",
        parsing_status: "SKIPPED",
        extraction_status: "SKIPPED",
      }),
    ).toContain("Proprietary or binary");
  });



  it("maps assistant engineering metadata", () => {

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

        artifacts: [

          {

            id: "a1",

            name: "Analysis Report",

            artifact_type: "engineering_report",

            href: "/workspace/reports",

          },

        ],

        status_events: ["Building engineering context", "Validating results"],

        actions: [{ label: "View Results", href: "/workspace/results" }],

      },

      created_at: "2026-01-01T00:00:00Z",

    });

    expect(mapped.engineeringResult?.artifacts[0].name).toBe("Analysis Report");

    expect(mapped.engineeringResult?.statusEvents.length).toBe(2);

    expect(mapped.engineeringResult?.approvalRequestId).toBeNull();

  });



  it("maps pending approval metadata for in-chat review", () => {

    const mapped = mapBackendMessage({

      id: "m2",

      conversation_id: "c1",

      role: "assistant",

      content: "Requires human approval.",

      attachments: [],

      metadata: {

        mode: "agent_execution",

        progress: "awaiting_approval",

        requires_approval: true,

        approval_request_id: "approval-99",

        selected_capability: "Structural Modeling Agent",

        actions: [{ label: "Review approval", href: "/workspace/approvals?review=approval-99" }],

      },

      created_at: "2026-01-01T00:00:00Z",

    });

    expect(mapped.engineeringResult?.requiresApproval).toBe(true);

    expect(mapped.engineeringResult?.approvalRequestId).toBe("approval-99");

    expect(pendingChatApprovalId(mapped.engineeringResult)).toBe("approval-99");

    expect(

      workspaceActionsForChat(mapped.engineeringResult?.actions ?? [], true),

    ).toEqual([]);

  });



  it("does not treat completed executions as pending chat approval", () => {

    expect(

      pendingChatApprovalId({

        requiresApproval: true,

        approvalRequestId: "approval-1",

        executionStatus: "completed",

      }),

    ).toBeNull();

    expect(

      pendingChatApprovalId({

        requiresApproval: false,

        approvalRequestId: "approval-1",

        executionStatus: "awaiting_approval",

      }),

    ).toBeNull();

  });



  it("shows disclaimer for engineering completion responses", () => {

    expect(shouldShowEngineeringDisclaimer("Analysis completed.")).toBe(true);

    expect(shouldShowEngineeringDisclaimer("Hello there")).toBe(false);

  });



  it("extracts workspace actions from assistant metadata", () => {

    const message: ChatMessage = {

      id: "m1",

      conversation_id: "c1",

      role: "assistant",

      content: "Done",

      attachments: [],

      metadata: {

        actions: [{ label: "View Results", href: "/workspace/results" }],

      },

      created_at: "2026-01-01T00:00:00Z",

    };

    expect(extractChatActions(message)).toEqual([

      { label: "View Results", href: "/workspace/results" },

    ]);

  });



  it("labels attachment processing states", () => {

    expect(

      attachmentStatusLabel({

        file_id: "f",

        filename: "a.pdf",

        file_type: "PDF",

        content_type: "application/pdf",

        status: "processing",

        parsing_status: "IN_PROGRESS",

        extraction_status: "PENDING",

      }),

    ).toBe("Processing…");

  });



  it("documents that agent-run streaming uses SSE", () => {

    expect(STREAMING_CAPABILITIES.supported).toBe(true);
    expect(STREAMING_CAPABILITIES.transport).toBe("sse");

  });

});



describe("chat api module", () => {

  it("exports chat and conversation API functions", async () => {

    const chatApi = await import("../lib/chat-api");

    expect(chatApi.sendChatMessage).toBeTypeOf("function");
    expect(chatApi.streamChatMessage).toBeTypeOf("function");

    expect(chatApi.listConversations).toBeTypeOf("function");

    expect(chatApi.uploadConversationAttachment).toBeTypeOf("function");

  });

});



describe("chat page modules", () => {

  it("loads chat workspace and composer modules", async () => {

    const workspace = await import("../components/chat/ChatWorkspace");

    const composer = await import("../components/chat/ChatComposer");

    const artifact = await import("../components/chat/ArtifactCard");

    const messageContent = await import("../components/chat/MessageContent");
    const resultCard = await import("../components/chat/EngineeringResultCard");
    const aciCard = await import("../components/chat/AciRcBeamResultCard");
    const contextPanel = await import("../components/chat/ChatContextPanel");
    const visualization = await import("../components/chat/demo/RCDemoVisualization");
    const progress = await import("../components/chat/AgentProgress");
    const toolCard = await import("../components/chat/ToolExecutionCard");

    expect(workspace.default).toBeTypeOf("function");

    expect(composer.ChatComposer).toBeTypeOf("function");

    expect(artifact.ArtifactCard).toBeTypeOf("function");

    expect(messageContent.MessageContent).toBeTypeOf("function");
    expect(resultCard.EngineeringResultCard).toBeTypeOf("function");
    expect(aciCard.AciRcBeamResultCard).toBeTypeOf("function");
    expect(contextPanel.ChatContextPanel).toBeTypeOf("function");
    expect(visualization.RCDemoVisualization).toBeTypeOf("function");
    expect(progress.AgentProgress).toBeTypeOf("function");
    expect(toolCard.ToolExecutionCard).toBeTypeOf("function");

  });



  it("keeps chat workspace isolated from meta-agent modules", () => {
    const workspaceSource = readFileSync(
      resolve(__dirname, "../components/chat/ChatWorkspace.tsx"),
      "utf8",
    );
    expect(workspaceSource).not.toContain("meta-agent");
    expect(workspaceSource).not.toContain("MetaAgent");
  });

});



describe("useChat hook", () => {

  it("exports conversation state hook", async () => {

    const hook = await import("../hooks/useChat");

    expect(hook.useChat).toBeTypeOf("function");

  });

});



describe("responsive sidebar behavior", () => {
  it("sidebar module exposes mobile open state contract via props", async () => {
    const sidebar = await import("../components/chat/ChatSidebar");
    expect(sidebar.ChatSidebar).toBeTypeOf("function");
  });

  it("exposes Approvals, Reports, Memory, and Traceability workspace links", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/ChatSidebar.tsx"),
      "utf8",
    );
    expect(source).toContain('href="/workspace/approvals"');
    expect(source).toContain('href="/workspace/reports"');
    expect(source).toContain('href="/workspace/memory"');
    expect(source).toContain('href="/workspace/learning"');
    expect(source).toContain('href="/workspace/traceability"');
    expect(source).toContain('href="/workspace/agents"');
    expect(source).toContain('href="/workspace/agents/builder"');
    expect(source).toContain("New Project");
  });
});

describe("prominent prompt composer", () => {
  it("ChatComposer exposes prominent variant with engineering placeholder", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/ChatComposer.tsx"),
      "utf8",
    );
    expect(source).toContain('variant?: "default" | "prominent"');
    expect(source).toContain("Tell StructuralAIAgent what you want to accomplish");
    expect(source).toContain("Send");
  });

  it("ChatWorkspace shows centered prompt when conversation has not started", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/ChatWorkspace.tsx"),
      "utf8",
    );
    expect(source).toContain("shouldShowProminentPrompt");
    expect(source).toContain("Tell StructuralAIAgent what you want to accomplish.");
    expect(source).toContain("Describe a structural engineering task");
    expect(source).toContain('variant="prominent"');
    expect(source).toContain("PromptExamples");
  });

  it("shows hero only for empty idle conversations", () => {
    expect(
      shouldShowProminentPrompt({ loadingMessages: false, messageCount: 0, busy: false }),
    ).toBe(true);
    expect(
      shouldShowProminentPrompt({ loadingMessages: false, messageCount: 2, busy: false }),
    ).toBe(false);
    expect(
      shouldShowProminentPrompt({ loadingMessages: false, messageCount: 0, busy: true }),
    ).toBe(false);
    expect(
      shouldShowProminentPrompt({ loadingMessages: true, messageCount: 0, busy: false }),
    ).toBe(false);
  });

  it("exports engineering-specific example prompts", () => {
    expect(ENGINEERING_PROMPT_EXAMPLES.length).toBe(6);
    expect(ENGINEERING_PROMPT_EXAMPLES[0]).toContain("simply supported reinforced concrete beam");
    expect(ENGINEERING_PROMPT_EXAMPLES[1]).toContain("ACI 318");
    expect(ENGINEERING_PROMPT_EXAMPLES[4]).toContain("governing structural requirements");
    expect(ENGINEERING_PROMPT_EXAMPLES[5]).toContain("پیلوت");
  });

  it("PromptExamples populates composer via onSelect callback", async () => {
    const examples = await import("../components/chat/PromptExamples");
    expect(examples.PromptExamples).toBeTypeOf("function");
    const source = readFileSync(
      resolve(__dirname, "../components/chat/PromptExamples.tsx"),
      "utf8",
    );
    expect(source).toContain("onSelect(example)");
    expect(source).not.toContain("handleSend");
  });

  it("ChatComposer exposes accessible labels for prompt and actions", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/ChatComposer.tsx"),
      "utf8",
    );
    expect(source).toContain('aria-label="Type your structural engineering request"');
    expect(source).toContain('aria-label="Attach engineering file"');
    expect(source).toContain('aria-label={busy ? "Sending message" : "Send message"}');
    expect(source).toContain("ENGINEERING_FILE_ACCEPT");
  });

  it("useChat sends through existing sendChatMessage API", () => {
    const source = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(source).toContain("sendChatMessage");
    expect(source).toContain("createConversation");
  });

  it("rejects empty prompt without attachments", () => {
    expect(canSendMessage("", [])).toBe(false);
    expect(canSendMessage("   ", [])).toBe(false);
  });

  it("Enter sends and Shift+Enter keeps newline behavior", () => {
    const onSend = vi.fn();
    handleComposerKeyDown({ key: "Enter", shiftKey: false, preventDefault: vi.fn() }, onSend);
    expect(onSend).toHaveBeenCalledOnce();

    onSend.mockClear();
    handleComposerKeyDown({ key: "Enter", shiftKey: true, preventDefault: vi.fn() }, onSend);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("sends prompt and attachments together via buildSendPayload", () => {
    const payload = buildSendPayload("Analyze drift", [
      {
        localId: "1",
        file: new File(["x"], "model.pdf"),
        uploaded: {
          file_id: "file-99",
          filename: "model.pdf",
          file_type: "PDF",
          content_type: "application/pdf",
          status: "ready",
          parsing_status: "COMPLETE",
          extraction_status: "COMPLETE",
        },
      },
    ]);
    expect(payload.content).toBe("Analyze drift");
    expect(payload.attachment_file_ids).toEqual(["file-99"]);
  });

  it("maps assistant responses from backend chat metadata", () => {
    const mapped = mapBackendMessage({
      id: "m2",
      conversation_id: "c1",
      role: "assistant",
      content: "**Status:** completed",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "completed",
        selected_capability: "Analysis Agent",
      },
      created_at: "2026-01-01T00:00:00Z",
    });
    expect(mapped.content).toContain("completed");
    expect(mapped.engineeringResult?.executionStatus).toBe("completed");
    expect(mapped.engineeringResult?.demoResults).toBeNull();
  });

  it("maps demo RC beam engineering results from chat metadata", () => {
    const mapped = mapBackendMessage({
      id: "m3",
      conversation_id: "c1",
      role: "assistant",
      content: "Demo calculation",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "completed",
        selected_capability: "Analysis Agent",
        engineering_results: {
          kind: "demo_rc_beam",
          status: "completed",
          demo: true,
          disclaimer: "Demo calculation. Final engineering decisions require verification by a qualified engineer.",
          code: "Demo / configured project code profile",
          fields: [
            { label: "Maximum Moment", value: "90.00", unit: "kN·m" },
            { label: "Maximum Shear", value: "60.00", unit: "kN" },
          ],
          assumptions: ["Simply supported single span"],
          warnings: [],
        },
      },
      created_at: "2026-01-01T00:00:00Z",
    });
    expect(mapped.engineeringResult?.demoResults?.fields[0]?.value).toBe("90.00");
    expect(mapped.engineeringResult?.demoResults?.fields[1]?.value).toBe("60.00");
    expect(mapped.engineeringResult?.demoResults?.disclaimer).toContain("Demo calculation");
    expect(mapped.engineeringResult?.aciBeamResults).toBeNull();
  });

  it("maps ACI RC beam engineering results from chat metadata", () => {
    const mapped = mapBackendMessage({
      id: "m4",
      conversation_id: "c1",
      role: "assistant",
      content: "ACI check",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "awaiting_approval",
        selected_capability: "Concrete Design Agent",
        engineering_results: {
          kind: "aci_rc_beam",
          status: "PASS",
          demo: false,
          disclaimer: "Simplified ACI 318-25 beam check.",
          code: "ACI CODE-318-25",
          plugin_id: "ACI318-25",
          input_units: "SI (mm, MPa, kN, kN·m, mm²)",
          fields: [{ label: "φMn", value: "217.59", unit: "kN·m" }],
          assumptions: ["Whitney rectangular stress block"],
          warnings: [],
          missing: [],
          inputs: { width_mm: 300, as_mm2: 1500, fc_mpa: 25, fy_mpa: 400 },
          demands: { mu_kn_m: 90, vu_kn: 60 },
          results: {
            phi_mn_kn_m: 217.59,
            phi_vc_kn: 84.1,
            flexure_outcome: "PASS",
            shear_outcome: "PASS",
            flexure_utilization: 0.414,
          },
        },
      },
      created_at: "2026-01-01T00:00:00Z",
    });
    expect(mapped.engineeringResult?.demoResults).toBeNull();
    expect(mapped.engineeringResult?.aciBeamResults?.kind).toBe("aci_rc_beam");
    expect(mapped.engineeringResult?.aciBeamResults?.numericResults?.phiMnKnM).toBe(217.59);
    expect(mapped.engineeringResult?.aciBeamResults?.numericResults?.muKnM).toBe(90);
    expect(mapped.engineeringResult?.aciBeamResults?.inputs?.asMm2).toBe(1500);
  });

  it("maps incomplete ACI results without inventing numbers", () => {
    const mapped = mapBackendMessage({
      id: "m5",
      conversation_id: "c1",
      role: "assistant",
      content: "Need inputs",
      attachments: [],
      metadata: {
        mode: "agent_execution",
        progress: "completed",
        engineering_results: {
          kind: "aci_rc_beam",
          status: "MISSING_REQUIRED_INPUT",
          demo: false,
          missing: ["Width b", "Tension reinforcement area As"],
          fields: [],
          assumptions: [],
          warnings: [],
          results: {},
        },
      },
      created_at: "2026-01-01T00:00:00Z",
    });
    expect(mapped.engineeringResult?.aciBeamResults?.status).toBe("MISSING_REQUIRED_INPUT");
    expect(mapped.engineeringResult?.aciBeamResults?.missing).toContain("Width b");
    expect(mapped.engineeringResult?.aciBeamResults?.numericResults?.phiMnKnM).toBeNull();
  });

  it("useChat exposes busy state for loading indicator", () => {
    const source = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(source).toContain("setBusy(true)");
    expect(source).toContain("executionPhase");
  });
});

describe("first request UX", () => {
  it("hides hero once an optimistic user message exists", () => {
    expect(
      shouldShowProminentPrompt({ loadingMessages: false, messageCount: 1, busy: false }),
    ).toBe(false);
    expect(
      shouldShowProminentPrompt({ loadingMessages: false, messageCount: 1, busy: true }),
    ).toBe(false);
  });

  it("builds optimistic user messages immediately on send", () => {
    const optimisticId = createOptimisticMessageId();
    expect(optimisticId.startsWith("optimistic-")).toBe(true);

    const message = buildOptimisticUserMessage(
      optimisticId,
      "conv-1",
      "Analyze drift",
      [
        {
          localId: "a1",
          file: new File(["x"], "model.pdf"),
          uploaded: {
            file_id: "file-1",
            filename: "model.pdf",
            file_type: "PDF",
            content_type: "application/pdf",
            status: "ready",
            parsing_status: "COMPLETE",
            extraction_status: "COMPLETE",
          },
        },
      ],
    );

    expect(message.role).toBe("user");
    expect(message.content).toBe("Analyze drift");
    expect(message.attachments).toHaveLength(1);
    expect(isOptimisticMessage(message)).toBe(true);
  });

  it("replaces optimistic messages with persisted backend messages", () => {
    const optimisticId = createOptimisticMessageId();
    const optimistic = buildOptimisticUserMessage(optimisticId, "c1", "Hello", []);
    const userMessage: ChatMessage = {
      id: "u1",
      conversation_id: "c1",
      role: "user",
      content: "Hello",
      attachments: [],
      metadata: {},
      created_at: "2026-01-01T00:00:00Z",
    };
    const assistantMessage: ChatMessage = {
      id: "a1",
      conversation_id: "c1",
      role: "assistant",
      content: "Hi",
      attachments: [],
      metadata: {},
      created_at: "2026-01-01T00:00:01Z",
    };

    const next = replaceOptimisticMessages(
      [optimistic],
      optimisticId,
      userMessage,
      assistantMessage,
    );
    expect(next).toHaveLength(2);
    expect(next[0].id).toBe("u1");
    expect(next[1].id).toBe("a1");
    expect(isOptimisticMessage(next[0])).toBe(false);
  });

  it("prevents duplicate send while busy in useChat", () => {
    const source = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(source).toMatch(/async function handleSend\(\)[\s\S]*?if \(busy\)[\s\S]*?return;/);
    expect(source).toContain("buildOptimisticUserMessage");
    expect(source).toContain("setContent(\"\")");
    expect(source).toContain("setPendingAttachments([])");
  });

  it("surfaces chat API errors with retry without duplicating optimistic messages", () => {
    const source = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(source).toContain("formatChatError(err)");
    expect(source).toContain("setRetryRequest(request)");
    expect(source).toContain("async function handleRetry()");
    expect(source).toContain("{ isRetry: true }");
    expect(source).not.toMatch(
      /catch \(err\)[\s\S]*?setContent\(request\.message\)/,
    );
  });

  it("restores composer content and attachments on dismiss after failure", () => {
    const source = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(source).toContain("handleDismissError");
    expect(source).toContain("setContent(retryRequest.message)");
    expect(source).toContain("setPendingAttachments(retryRequest.pendingAttachments)");
    expect(source).toContain("retryRequest.optimisticMessageId");
    expect(source).toContain("optimisticAssistantId");
  });

  it("transitions from hero to conversation panel in ChatWorkspace", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/ChatWorkspace.tsx"),
      "utf8",
    );
    expect(source).toContain("chat-conversation-panel");
    expect(source).toContain("handleRetry");
    expect(source).toContain('role="alert"');
    expect(source).toContain("composerInputRef");
    expect(source).toContain("setSelectionRange");
  });

  it("shows processing state in ChatThread with accessible live region", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/ChatThread.tsx"),
      "utf8",
    );
    expect(source).toContain('aria-live="polite"');
    expect(source).toContain("Processing your engineering request");
    expect(source).toContain("chat-typing-indicator");
    expect(source).toContain("ApprovalReviewPanel");
  });

  it("example prompt populates composer and focuses without auto-send", () => {
    const workspace = readFileSync(
      resolve(__dirname, "../components/chat/ChatWorkspace.tsx"),
      "utf8",
    );
    const examples = readFileSync(
      resolve(__dirname, "../components/chat/PromptExamples.tsx"),
      "utf8",
    );
    expect(workspace).toContain("handleExampleSelect");
    expect(workspace).toContain("chat.setContent(text)");
    expect(workspace).toContain("input.focus()");
    expect(examples).not.toContain("onSend");
    expect(examples).not.toContain("handleSend");
  });

  it("preserves attachment ids in pending send requests", () => {
    const source = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(source).toContain("pendingAttachments: attachmentSnapshot");
    expect(source).toContain("attachments: payload.attachment_file_ids");
  });

  it("includes subtle conversation panel transition styles", () => {
    const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf8");
    expect(css).toContain(".chat-conversation-panel");
    expect(css).toContain("chat-panel-in");
  });

  it("ChatComposer exposes accessibility labels and busy state", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/ChatComposer.tsx"),
      "utf8",
    );
    expect(source).toContain('aria-label="Type your structural engineering request"');
    expect(source).toContain('aria-label="Attach engineering file"');
    expect(source).toContain('aria-label={busy ? "Sending message" : "Send message"}');
    expect(source).toContain("aria-busy={busy}");
    expect(source).toContain("aria-disabled={busy}");
  });

  it("hero layout uses engineering-focused copy and example grid", () => {
    const workspace = readFileSync(
      resolve(__dirname, "../components/chat/ChatWorkspace.tsx"),
      "utf8",
    );
    const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf8");
    expect(workspace).toContain("chat-hero-intro");
    expect(workspace).toContain("Structural Engineering AI");
    expect(css).toContain(".chat-prompt-examples-label");
    expect(css).toContain("grid-template-columns: 1fr 1fr");
  });
});

