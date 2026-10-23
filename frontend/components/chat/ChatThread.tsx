"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import { ApprovalReviewPanel } from "@/components/agents/ApprovalReviewPanel";
import type { ChatMessage as ApiChatMessage } from "@/lib/chat-api";
import {
  extractChatActions,
  pendingChatApprovalId,
  shouldShowEngineeringDisclaimer,
  workspaceActionsForChat,
} from "@/lib/chat";
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
}: ChatThreadProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, loadingMessages]);

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
        <h2>StructuralAIAgent</h2>
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

  return (
    <div className="chat-thread">
      {messages.map((rawMessage) => {
        const message = toUiMessage(rawMessage);
        return (
          <article
            key={message.id}
            className={
              message.role === "user" ? "chat-message chat-message-user" : "chat-message chat-message-assistant"
            }
          >
            <p className="chat-message-role">{message.role === "user" ? "You" : "Agent"}</p>
            <div className="chat-message-body">
              {message.attachments.length > 0 ? (
                <div className="chat-message-attachments">
                  {rawMessage.attachments.map((attachment) => (
                    <AttachmentChip key={attachment.file_id} attachment={attachment} />
                  ))}
                </div>
              ) : null}
              <MessageContent content={message.content} />
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
          </article>
        );
      })}
      {busy && !hasStreamingAssistant ? (
        <article className="chat-message chat-message-assistant" aria-live="polite" aria-busy="true">
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
    </div>
  );
}
