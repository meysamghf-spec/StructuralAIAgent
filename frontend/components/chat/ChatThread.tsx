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
import { chatT, conversationLang, dirOf, messageLang, type ChatLang } from "@/lib/chat-i18n";
import { mapBackendMessage } from "@/lib/chat-mappers";
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

  const scroller = useCallback(
    () => (threadRef.current?.closest(".chat-main-body") as HTMLElement | null) ?? null,
    [],
  );

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
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [scroller, loadingMessages, messages.length === 0]);

  const firstMessageId = messages[0]?.id;
  useEffect(() => {
    // A conversation was opened/loaded: jump straight to the newest message (no animation).
    if (loadingMessages) {
      return;
    }
    stickRef.current = true;
    setShowJump(false);
    endRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [loadingMessages, firstMessageId]);

  useEffect(() => {
    // Auto-scroll only while the reader is at the bottom (so streaming does not yank them away).
    if (stickRef.current) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, busy, loadingMessages]);

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

  const convLang = conversationLang(messages);
  const hasStreamingAssistant = messages.some(
    (message) => message.role === "assistant" && message.metadata?.streaming === true,
  );

  return (
    <div className="chat-thread" ref={threadRef}>
      {messages.map((rawMessage, messageIndex) => {
        const message = toUiMessage(rawMessage);
        // language/direction of THIS message: the backend tag, else the text; assistant cards follow the user's language
        const lang: ChatLang = messageLang(
          message.content,
          rawMessage.metadata as Record<string, unknown> | null,
          rawMessage.role === "assistant" ? convLang : null,
        );
        const isLastAssistant =
          message.role === "assistant" && messageIndex === messages.length - 1 && !busy;
        const tokenStreaming = rawMessage.metadata?.token_streaming === true && rawMessage.metadata?.streaming === true;
        return (
          <article
            key={message.id}
            className={
              message.role === "user" ? "chat-message chat-message-user" : "chat-message chat-message-assistant"
            }
            dir={dirOf(lang)}
            lang={lang}
          >
            <div className="chat-message-avatar" aria-hidden="true">{message.role === "user" ? chatT(lang, "You") : "AI"}</div>
            <p className="chat-message-role">{message.role === "user" ? chatT(lang, "You") : chatT(lang, "Agent")}</p>
            <div className="chat-message-body">
              {message.attachments.length > 0 ? (
                <div className="chat-message-attachments">
                  {rawMessage.attachments.map((attachment) => (
                    <AttachmentChip key={attachment.file_id} attachment={attachment} />
                  ))}
                </div>
              ) : null}
              {message.role === "assistant" && rawMessage.metadata?.streaming === true && !message.content.trim() ? (
                <div className="chat-typing-indicator" aria-label={chatT(lang, "Assistant is responding")}><span /><span /><span /></div>
              ) : null}
              <MessageContent content={message.content} lang={lang} />
              {tokenStreaming ? <span className="chat-stream-caret" aria-hidden="true" /> : null}
              {message.role === "assistant" && rawMessage.metadata?.stopped === true ? (
                <p className="muted chat-stopped-note">{chatT(lang, "Stopped")}</p>
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
                    <span className="chat-progress-badge">{chatT(lang, message.engineeringResult.selectedCapability)}</span>
                  ) : null}
                  {message.engineeringResult.executionStatus ? (
                    <span className="chat-progress-badge">
                      {chatT(lang, message.engineeringResult.executionStatus.replace(/_/g, " "))}
                    </span>
                  ) : null}
                  {message.engineeringResult.requiresApproval ? (
                    <span className="chat-progress-badge warning">{chatT(lang, "Requires approval")}</span>
                  ) : null}
                  {message.engineeringResult.agentRun ? (
                    <>
                      <AgentProgress steps={message.engineeringResult.agentRun.steps} lang={lang} />
                      <AgentContextStrip
                        context={message.engineeringResult.agentRun.context}
                        projectName={projectName}
                        lang={lang}
                      />
                      {message.engineeringResult.agentRun.tools.map((tool) => (
                        <ToolExecutionCard key={tool.id} tool={tool} lang={lang} />
                      ))}
                      {message.engineeringResult.agentRun.error ? (
                        <AgentErrorCard error={message.engineeringResult.agentRun.error} lang={lang} />
                      ) : null}
                    </>
                  ) : message.engineeringResult.statusEvents.length > 0 ? (
                    <ul className="chat-status-events" dir={dirOf(lang)}>
                      {message.engineeringResult.statusEvents.map((event) => (
                        <li key={event}>{chatT(lang, event)}</li>
                      ))}
                    </ul>
                  ) : null}
                  {message.engineeringResult.demoResults ? (
                    <EngineeringResultCard results={message.engineeringResult.demoResults} lang={lang} />
                  ) : null}
                  {message.engineeringResult.frame3dResults ? (
                    <Frame3dResultCard results={message.engineeringResult.frame3dResults} />
                  ) : null}
                  {message.engineeringResult.aciBeamResults ? (
                    <AciRcBeamResultCard results={message.engineeringResult.aciBeamResults} lang={lang} />
                  ) : null}
                  {message.engineeringResult.artifacts.length > 0 ? (
                    <div className="chat-artifacts">
                      {message.engineeringResult.artifacts.map((artifact) => (
                        <ArtifactCard key={artifact.id} artifact={artifact} lang={lang} />
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
                          <div className="chat-inline-approval" dir={dirOf(lang)}>
                            <p className="agent-approval-heading">{chatT(lang, "Approval required")}</p>
                            <ApprovalReviewPanel
                              projectId={projectId}
                              approvalRequestId={approvalId}
                              onResolved={onApprovalResolved ?? (() => undefined)}
                              lang={lang}
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
                                {chatT(lang, action.label)}
                              </Link>
                            ))}
                          </div>
                        ) : null}
                      </>
                    );
                  })()}
                  {shouldShowEngineeringDisclaimer(message.content) ? (
                    <p className="muted chat-disclaimer">
                      {chatT(
                        lang,
                        "Engineering outputs require review by a qualified professional before use in construction documents.",
                      )}
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
                  aria-label={chatT(lang, "Copy")}
                  onClick={() => copyMessage(message.id, message.content)}
                >
                  {chatT(lang, copiedId === message.id ? "Copied ✓" : "Copy")}
                </button>
                {isLastAssistant && onRegenerate ? (
                  <button type="button" className="chat-tool-button" aria-label={chatT(lang, "Regenerate")} onClick={onRegenerate}>
                    {chatT(lang, "Regenerate")}
                  </button>
                ) : null}
              </div>
            ) : null}
          </article>
        );
      })}
      {busy && !hasStreamingAssistant ? (
        <article className="chat-message chat-message-assistant" aria-live="polite" aria-busy="true" dir={dirOf(convLang)} lang={convLang}>
          <p className="chat-message-role">{chatT(convLang, "Agent")}</p>
          <div className="chat-message-body">
            <p className="muted">{chatT(convLang, statusLabel ?? "Processing your engineering request…")}</p>
            <AgentProgress steps={liveProgressSteps(executionPhase, statusLabel)} lang={convLang} />
            {executionPhase !== "idle" && executionPhase !== "error" ? (
              <div className="chat-typing-indicator" aria-label={chatT(convLang, "Assistant is responding")}>
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
        <button type="button" className="chat-jump-latest" onClick={jumpToLatest} aria-label="Scroll to latest message" dir={dirOf(convLang)}>
          {chatT(convLang, "↓ Latest")}
        </button>
      ) : null}
    </div>
  );
}
