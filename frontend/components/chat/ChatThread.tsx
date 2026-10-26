"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApprovalReviewPanel } from "@/components/agents/ApprovalReviewPanel";
import type { ChatMessage as ApiChatMessage } from "@/lib/chat-api";
import {
  extractChatActions,
  pendingChatApprovalId,
  shouldShowEngineeringDisclaimer,
  workspaceActionsForChat,
} from "@/lib/chat";
import { mapBackendMessage } from "@/lib/chat-mappers";
import { countUserMessages, isManualScrollKey, lastUserMessageIndex, planReplyScroll, replyMessageIndex } from "@/lib/chat-scroll";
import type { AgentRunStep, ChatMessage as UiChatMessage, ExecutionPhase } from "@/lib/chat-types";

import { AgentContextStrip } from "./AgentContextStrip";
import { AgentErrorCard } from "./AgentErrorCard";
import { AgentProgress } from "./AgentProgress";
import { ArtifactCard } from "./ArtifactCard";
import { AttachmentChip } from "./AttachmentChip";
import { AciRcBeamResultCard } from "./AciRcBeamResultCard";
import { EngineeringResultCard } from "./EngineeringResultCard";
import { Frame3dResultCard } from "./Frame3dResultCard";
import { ChatDownloadsCard } from "./ChatDownloadsCard";
import { parseChatDownloads } from "@/lib/chat-actions";
import { AutocadDrawingCard } from "@/components/autocad/AutocadDrawingCard";
import { ArchitecturalSetViewer } from "@/components/autocad/ArchitecturalSetViewer";
import { StructuralSetView } from "@/components/autocad/StructuralSetView";
import { MessageContent } from "./MessageContent";
import { ToolExecutionCard } from "./ToolExecutionCard";

type ChatThreadProps = {
  messages: ApiChatMessage[];
  busy: boolean;
  loadingMessages: boolean;
  executionPhase: ExecutionPhase;
  statusLabel: string | null;
  projectId: string | null;
  projectName?: string | null;
  onApprovalResolved?: () => void;
  onRegenerate?: () => void;
};

function toUiMessage(message: ApiChatMessage): UiChatMessage {
  return mapBackendMessage(message);
}

function liveProgressSteps(phase: ExecutionPhase, statusLabel: string | null): AgentRunStep[] {
  if (phase === "uploading") {
    return [{ key: "upload", label: "Reading attached files", state: "current" }];
  }
  if (phase === "building_context") {
    return [{ key: "context", label: "Loading project context", state: "current" }];
  }
  if (phase === "processing") {
    return [
      {
        key: "understand",
        label: statusLabel ?? "Understanding request",
        state: "current",
      },
    ];
  }
  return [];
}

export function ChatThread({
  messages,
  busy,
  loadingMessages,
  executionPhase,
  statusLabel,
  projectId,
  projectName,
  onApprovalResolved,
  onRegenerate,
}: ChatThreadProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const [showJump, setShowJump] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Turn state for "show the START of the new answer": reset whenever the user sends a message.
  const turnRef = useRef<{ users: number; active: boolean; pinned: boolean; manual: boolean }>({
    users: 0,
    active: false,
    pinned: false,
    manual: false,
  });

  const scroller = useCallback((): HTMLElement | null => {
    // Nearest vertically scrolling ancestor: .chat-main-body on the chat page, .chat-dock-body in the dock.
    let node = threadRef.current?.parentElement ?? null;
    while (node) {
      const overflowY = window.getComputedStyle(node).overflowY;
      if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") {
        return node;
      }
      node = node.parentElement;
    }
    return null;
  }, []);

  useEffect(() => {
    const el = scroller();
    if (!el) {
      return;
    }
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      stickRef.current = nearBottom;
      setShowJump(!nearBottom);
    };
    // Any hand-driven scroll (wheel, touch, scrollbar drag, keys) means "do not fight me" for this answer.
    const markManual = () => {
      turnRef.current.manual = true;
    };
    const onMouseDown = (event: MouseEvent) => {
      if (event.target === el) {
        markManual(); // scrollbar drag
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (isManualScrollKey(event.key, target?.tagName, Boolean(target?.isContentEditable))) {
        markManual();
      }
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    el.addEventListener("wheel", markManual, { passive: true });
    el.addEventListener("touchmove", markManual, { passive: true });
    el.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      el.removeEventListener("scroll", onScroll);
      el.removeEventListener("wheel", markManual);
      el.removeEventListener("touchmove", markManual);
      el.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [scroller, loadingMessages, messages.length === 0]);

  const initRef = useRef(false);
  const loadedRef = useRef(false);
  const prevBusyRef = useRef(false);
  useEffect(() => {
    if (loadingMessages) {
      loadedRef.current = true;
      return;
    }
    const users = countUserMessages(messages);
    if (!initRef.current || loadedRef.current) {
      // First render or a conversation was opened/loaded: jump straight to the newest message (no animation).
      initRef.current = true;
      loadedRef.current = false;
      prevBusyRef.current = busy;
      turnRef.current = { users, active: false, pinned: false, manual: false };
      stickRef.current = true;
      setShowJump(false);
      endRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
      return;
    }
    const turn = turnRef.current;
    const busyStarted = busy && !prevBusyRef.current;
    prevBusyRef.current = busy;
    if (users > turn.users) {
      // The user just sent a message: keep scrolling to the bottom as before; the reply is handled below.
      turnRef.current = { users, active: true, pinned: false, manual: false };
      stickRef.current = true;
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    } else if (busyStarted && users === turn.users && users > 0) {
      // Regenerate / retry: a new reply for the same question starts streaming.
      turnRef.current = { users, active: true, pinned: false, manual: false };
    } else if (users < turn.users) {
      // "New chat" or messages removed: no reply to track.
      turnRef.current = { users, active: false, pinned: false, manual: false };
    }
    if (turnRef.current.active) {
      const turn = turnRef.current;
      // Reply is arriving/streaming: bring the question that triggered the answer to the top of the view, once, then leave the
      // scroll alone (no fighting a reader who scrolls manually while it streams).
      if (turn.manual || turn.pinned) {
        return;
      }
      const container = scroller();
      // The block that must be on screen = the user's question (aligned to the top) + the answer below it.
      const question = threadRef.current?.querySelector<HTMLElement>('[data-chat-question="true"]');
      const reply = threadRef.current?.querySelector<HTMLElement>('[data-chat-reply="true"]');
      if (!container || !question) {
        return;
      }
      const cRect = container.getBoundingClientRect();
      const qRect = question.getBoundingClientRect();
      const blockBottom = Math.max(qRect.bottom, reply?.getBoundingClientRect().bottom ?? 0);
      const style = window.getComputedStyle(container);
      const topOffset = (parseFloat(style.scrollPaddingTop) || 0) + 8;
      const plan = planReplyScroll({
        scrollTop: container.scrollTop,
        clientHeight: container.clientHeight,
        scrollHeight: container.scrollHeight,
        replyTop: qRect.top - cRect.top + container.scrollTop,
        replyHeight: blockBottom - qRect.top,
        topOffset,
        pinned: turn.pinned,
      });
      turn.pinned = plan.pinned;
      if (plan.top !== null) {
        container.scrollTo({ top: plan.top, behavior: "smooth" });
      }
      return;
    }
    // Not in a send turn (e.g. late server refresh): old behaviour, follow only while at the bottom.
    if (stickRef.current) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, busy, loadingMessages, scroller]);

  function jumpToLatest() {
    stickRef.current = true;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    setShowJump(false);
  }

  function copyMessage(id: string, text: string) {
    void navigator.clipboard?.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId((cur) => (cur === id ? null : cur)), 1500);
    });
  }

  if (loadingMessages) {
    return (
      <div className="chat-empty-state">
        <p className="muted">Loading conversation…</p>
      </div>
    );
  }

  if (messages.length === 0 && !busy) {
    return (
      <div className="chat-empty-state">
        <h2>SAIA</h2>
        <p className="muted">
          Describe your structural engineering problem, attach models, drawings, PDFs, or spreadsheets,
          and run analysis, design, validation, and reporting workflows from one conversation.
        </p>
      </div>
    );
  }

  const hasStreamingAssistant = messages.some(
    (message) => message.role === "assistant" && message.metadata?.streaming === true,
  );
  const replyIdx = replyMessageIndex(messages);
  const questionIdx = lastUserMessageIndex(messages);

  return (
    <div className="chat-thread" ref={threadRef}>
      {messages.map((rawMessage, messageIndex) => {
        const message = toUiMessage(rawMessage);
        const isLastAssistant =
          message.role === "assistant" && messageIndex === messages.length - 1 && !busy;
        const tokenStreaming = rawMessage.metadata?.token_streaming === true && rawMessage.metadata?.streaming === true;
        return (
          <article
            key={message.id}
            data-chat-reply={messageIndex === replyIdx ? "true" : undefined}
            data-chat-question={messageIndex === questionIdx ? "true" : undefined}
            className={
              message.role === "user" ? "chat-message chat-message-user" : "chat-message chat-message-assistant"
            }
          >
            <div className="chat-message-avatar" aria-hidden="true">{message.role === "user" ? "You" : "AI"}</div>
            <p className="chat-message-role">{message.role === "user" ? "You" : "Agent"}</p>
            <div className="chat-message-body">
              {message.attachments.length > 0 ? (
                <div className="chat-message-attachments">
                  {rawMessage.attachments.map((attachment) => (
                    <AttachmentChip key={attachment.file_id} attachment={attachment} />
                  ))}
                </div>
              ) : null}
              {message.role === "assistant" && rawMessage.metadata?.streaming === true && !message.content.trim() ? (
                <div className="chat-typing-indicator" aria-label="Assistant is responding"><span /><span /><span /></div>
              ) : null}
              <MessageContent content={message.content} />
              {tokenStreaming ? <span className="chat-stream-caret" aria-hidden="true" /> : null}
              {message.role === "assistant" && rawMessage.metadata?.stopped === true ? (
                <p className="muted chat-stopped-note">Stopped</p>
              ) : null}
              {message.role === "assistant" && parseChatDownloads(rawMessage.metadata) ? (
                <ChatDownloadsCard downloads={parseChatDownloads(rawMessage.metadata)!} />
              ) : null}
              {message.role === "assistant" && message.autocadResult ? (
                <AutocadDrawingCard
                  jobId={message.autocadResult.jobId}
                  title={message.autocadResult.title}
                  filename={message.autocadResult.filename}
                  kind={message.autocadResult.kind}
                  layers={message.autocadResult.layers}
                  review={message.autocadResult.review}
                  savedToProject={!!message.autocadResult.projectFileId}
                />
              ) : null}
              {message.role === "assistant" && message.archSet ? (
                <div className="chat-arch-set">
                  <ArchitecturalSetViewer set={message.archSet} compact />
                </div>
              ) : null}
              {message.role === "assistant" && message.structuralSet ? (
                <StructuralSetView set={message.structuralSet} compact />
              ) : null}
              {message.role === "assistant" && message.engineeringResult ? (
                <div className="chat-message-meta">
                  {message.engineeringResult.selectedCapability ? (
                    <span className="chat-progress-badge">{message.engineeringResult.selectedCapability}</span>
                  ) : null}
                  {message.engineeringResult.executionStatus ? (
                    <span className="chat-progress-badge">
                      {message.engineeringResult.executionStatus.replace(/_/g, " ")}
                    </span>
                  ) : null}
                  {message.engineeringResult.requiresApproval ? (
                    <span className="chat-progress-badge warning">Requires approval</span>
                  ) : null}
                  {message.engineeringResult.agentRun ? (
                    <>
                      <AgentProgress steps={message.engineeringResult.agentRun.steps} />
                      <AgentContextStrip
                        context={message.engineeringResult.agentRun.context}
                        projectName={projectName}
                      />
                      {message.engineeringResult.agentRun.tools.map((tool) => (
                        <ToolExecutionCard key={tool.id} tool={tool} />
                      ))}
                      {message.engineeringResult.agentRun.error ? (
                        <AgentErrorCard error={message.engineeringResult.agentRun.error} />
                      ) : null}
                    </>
                  ) : message.engineeringResult.statusEvents.length > 0 ? (
                    <ul className="chat-status-events">
                      {message.engineeringResult.statusEvents.map((event) => (
                        <li key={event}>{event}</li>
                      ))}
                    </ul>
                  ) : null}
                  {message.engineeringResult.demoResults ? (
                    <EngineeringResultCard results={message.engineeringResult.demoResults} />
                  ) : null}
                  {message.engineeringResult.frame3dResults ? (
                    <Frame3dResultCard results={message.engineeringResult.frame3dResults} />
                  ) : null}
                  {message.engineeringResult.aciBeamResults ? (
                    <AciRcBeamResultCard results={message.engineeringResult.aciBeamResults} />
                  ) : null}
                  {message.engineeringResult.artifacts.length > 0 ? (
                    <div className="chat-artifacts">
                      {message.engineeringResult.artifacts.map((artifact) => (
                        <ArtifactCard key={artifact.id} artifact={artifact} />
                      ))}
                    </div>
                  ) : null}
                  {(() => {
                    const approvalId = projectId ? pendingChatApprovalId(message.engineeringResult) : null;
                    const actions = workspaceActionsForChat(
                      message.engineeringResult.actions.length > 0
                        ? message.engineeringResult.actions
                        : extractChatActions(rawMessage),
                      Boolean(approvalId),
                    );
                    return (
                      <>
                        {approvalId && projectId ? (
                          <div className="chat-inline-approval">
                            <p className="agent-approval-heading">Approval required</p>
                            <ApprovalReviewPanel
                              projectId={projectId}
                              approvalRequestId={approvalId}
                              onResolved={onApprovalResolved ?? (() => undefined)}
                            />
                          </div>
                        ) : null}
                        {actions.length > 0 ? (
                          <div className="chat-message-actions">
                            {actions.map((action) => (
                              <Link
                                key={action.href}
                                href={action.href}
                                className="button secondary chat-action-link"
                              >
                                {action.label}
                              </Link>
                            ))}
                          </div>
                        ) : null}
                      </>
                    );
                  })()}
                  {shouldShowEngineeringDisclaimer(message.content) ? (
                    <p className="muted chat-disclaimer">
                      Engineering outputs require review by a qualified professional before use in
                      construction documents.
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
            {message.content.trim() && !rawMessage.metadata?.optimistic ? (
              <div className="chat-message-tools">
                <button
                  type="button"
                  className="chat-tool-button"
                  aria-label="Copy message"
                  onClick={() => copyMessage(message.id, message.content)}
                >
                  {copiedId === message.id ? "Copied ✓" : "Copy"}
                </button>
                {isLastAssistant && onRegenerate ? (
                  <button type="button" className="chat-tool-button" aria-label="Regenerate response" onClick={onRegenerate}>
                    Regenerate
                  </button>
                ) : null}
              </div>
            ) : null}
          </article>
        );
      })}
      {busy && !hasStreamingAssistant ? (
        <article
          className="chat-message chat-message-assistant"
          aria-live="polite"
          aria-busy="true"
          data-chat-reply={replyIdx === -1 ? "true" : undefined}
        >
          <p className="chat-message-role">Agent</p>
          <div className="chat-message-body">
            <p className="muted">{statusLabel ?? "Processing your engineering request…"}</p>
            <AgentProgress steps={liveProgressSteps(executionPhase, statusLabel)} />
            {executionPhase !== "idle" && executionPhase !== "error" ? (
              <div className="chat-typing-indicator" aria-label="Assistant is responding">
                <span />
                <span />
                <span />
              </div>
            ) : null}
          </div>
        </article>
      ) : null}
      <div ref={endRef} />
      {showJump ? (
        <button type="button" className="chat-jump-latest" onClick={jumpToLatest} aria-label="Scroll to latest message">
          ↓ Latest
        </button>
      ) : null}
    </div>
  );
}
