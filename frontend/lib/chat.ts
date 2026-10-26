import { randomId } from "@/lib/uuid";
/** Chat UI helpers and formatting. */

import type { ChatAction, ChatAttachment, ChatMessage } from "./chat-api";

export const ACTIVE_CONVERSATION_KEY = "structuralaiagent.activeConversationId";

export type PendingAttachment = {
  localId: string;
  file?: File;
  uploaded?: ChatAttachment;
  uploading?: boolean;
  error?: string;
  existingFile?: boolean;
};

export type MessageBlock =
  | { type: "paragraph"; text: string }
  | { type: "heading"; text: string; level?: number }
  | { type: "table"; header: string[]; rows: string[][]; align: Array<"left" | "right" | "center" | null> }
  | { type: "ordered-item"; text: string; n: string }
  | { type: "list-item"; text: string };

export function filterConversations<T extends { title: string }>(
  conversations: T[],
  query: string,
): T[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return conversations;
  }
  return conversations.filter((conversation) =>
    conversation.title.toLowerCase().includes(normalized),
  );
}

function splitRow(line: string): string[] {
  let t = line.trim();
  if (t.startsWith("|")) t = t.slice(1);
  if (t.endsWith("|") && !t.endsWith("\\|")) t = t.slice(0, -1);
  return t.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
}

const TABLE_SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

/** Minimal GitHub-style markdown: headings (#..######), bullet/ordered lists, pipe tables, **bold**. */
export function parseMessageContent(content: string): MessageBlock[] {
  const lines = content.split("\n");
  const blocks: MessageBlock[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.includes("|") && i + 1 < lines.length && TABLE_SEPARATOR.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      const header = splitRow(trimmed);
      const align = splitRow(lines[i + 1]).map((c) =>
        c.startsWith(":") && c.endsWith(":") ? "center" : c.endsWith(":") ? "right" : c.startsWith(":") ? "left" : null,
      );
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim().includes("|") && lines[i].trim() !== "") {
        const cells = splitRow(lines[i]);
        rows.push(header.map((_, k) => cells[k] ?? ""));
        i++;
      }
      i--;
      blocks.push({ type: "table", header, rows, align });
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (h) {
      blocks.push(h[1].length === 3 ? { type: "heading", text: h[2] } : { type: "heading", text: h[2], level: h[1].length });
      continue;
    }
    if (/^[-*+]\s+/.test(trimmed)) {
      blocks.push({ type: "list-item", text: trimmed.replace(/^[-*+]\s+/, "") });
      continue;
    }
    const o = /^(\d+)[.)]\s+(.*)$/.exec(trimmed);
    if (o) {
      blocks.push({ type: "ordered-item", n: o[1], text: o[2] });
      continue;
    }
    blocks.push({ type: "paragraph", text: line });
  }
  return blocks;
}

export function renderInlineMarkdown(text: string): Array<string | { bold: string }> {
  const parts: Array<string | { bold: string }> = [];
  const pattern = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push({ bold: match[1] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length > 0 ? parts : [text];
}

export function attachmentLimitationNote(attachment: ChatAttachment): string | null {
  if (attachment.parsing_status === "FAILED" || attachment.extraction_status === "FAILED") {
    return "Extraction failed. The file is stored but its content was not parsed.";
  }
  const filename = attachment.filename.toLowerCase();
  const proprietaryExtensions = [".edb", ".sdb", ".f2k", ".dwg", ".dxf"];
  if (
    proprietaryExtensions.some((extension) => filename.endsWith(extension)) &&
    attachment.extraction_status !== "COMPLETE"
  ) {
    return "Proprietary or binary engineering format — automated extraction is not available.";
  }
  if (
    attachment.parsing_status === "SKIPPED" ||
    attachment.extraction_status === "SKIPPED"
  ) {
    return "This file type is not automatically parsed. Content understanding is limited.";
  }
  if (attachment.extraction_status === "PENDING" || attachment.extraction_status === "IN_PROGRESS") {
    return "Extraction is still in progress.";
  }
  return null;
}

export function shouldShowProminentPrompt(options: {
  loadingMessages: boolean;
  messageCount: number;
  busy: boolean;
}): boolean {
  return !options.loadingMessages && options.messageCount === 0 && !options.busy;
}

export type PendingSendRequest = {
  message: string;
  conversation_id?: string;
  project_id?: string;
  attachments: string[];
  mode?: string;
  optimisticMessageId: string;
  pendingAttachments: PendingAttachment[];
};

export function createOptimisticMessageId(): string {
  return `optimistic-${randomId()}`;
}

export function buildOptimisticUserMessage(
  optimisticId: string,
  conversationId: string,
  content: string,
  attachments: PendingAttachment[],
): ChatMessage {
  return {
    id: optimisticId,
    conversation_id: conversationId,
    role: "user",
    content,
    attachments: attachments
      .filter((item) => item.uploaded)
      .map((item) => item.uploaded as ChatAttachment),
    metadata: { optimistic: true },
    created_at: new Date().toISOString(),
  };
}

export function isOptimisticMessage(message: ChatMessage): boolean {
  return message.metadata?.optimistic === true;
}

export function optimisticAssistantId(optimisticUserId: string): string {
  return `${optimisticUserId}-assistant`;
}

export function buildOptimisticAssistantMessage(
  optimisticUserId: string,
  conversationId: string,
): ChatMessage {
  return {
    id: optimisticAssistantId(optimisticUserId),
    conversation_id: conversationId,
    role: "assistant",
    content: "",
    attachments: [],
    metadata: {
      optimistic: true,
      streaming: true,
      mode: "agent_execution",
      agent_run: {
        lifecycle: "planning",
        current_step: "understand",
        progress: "queued",
        steps: [{ key: "understand", label: "Understanding request", state: "current" }],
        tools: [],
        context: { conversation: true, project: false, files: [], indexed_document_count: 0 },
        error: null,
      },
    },
    created_at: new Date().toISOString(),
  };
}

export function replaceOptimisticMessages(
  messages: ChatMessage[],
  optimisticId: string,
  userMessage: ChatMessage,
  assistantMessage: ChatMessage,
): ChatMessage[] {
  return [
    ...messages.filter(
      (message) => message.id !== optimisticId && message.id !== optimisticAssistantId(optimisticId),
    ),
    userMessage,
    assistantMessage,
  ];
}

export function getStoredActiveConversationId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACTIVE_CONVERSATION_KEY);
}

export function storeActiveConversationId(conversationId: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  if (conversationId) {
    window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId);
  } else {
    window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  }
}

export function extractChatActions(message: ChatMessage): ChatAction[] {
  const raw = message.metadata?.actions;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.filter(
    (item): item is ChatAction =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as ChatAction).label === "string" &&
      typeof (item as ChatAction).href === "string",
  );
}

export function attachmentStatusLabel(attachment: ChatAttachment | PendingAttachment): string {
  if ("uploading" in attachment) {
    if (attachment.uploading) {
      return "Uploading…";
    }
    if (attachment.error) {
      return "Failed";
    }
    if (attachment.uploaded) {
      return attachmentStatusLabel(attachment.uploaded);
    }
    return "Ready";
  }

  if ("status" in attachment) {
    switch (attachment.status) {
      case "uploading":
        return "Uploading…";
      case "processing":
        return "Processing…";
      case "failed":
        return "Failed";
      default:
        return "Ready";
    }
  }

  return "Ready";
}

export const ATTACHMENT_ONLY_INSTRUCTION = "Analyze this file";

export function isAttachmentReady(item: PendingAttachment): boolean {
  return Boolean(item.uploaded) && !item.error && !item.uploading;
}

export function hasUploadingAttachment(attachments: PendingAttachment[]): boolean {
  return attachments.some((item) => item.uploading);
}

/** Send is enabled with text and/or a ready attachment, and only blocked while an upload is in flight. */
export function canSendMessage(content: string, attachments: PendingAttachment[]): boolean {
  const hasText = content.trim().length > 0;
  const hasReadyFiles = attachments.some(isAttachmentReady);
  return (hasText || hasReadyFiles) && !hasUploadingAttachment(attachments);
}

export type SendBlockReason = "uploading" | "upload_failed" | "empty" | null;

/** Explains why Send is disabled so the composer can say it instead of silently greying out. */
export function sendBlockReason(
  content: string,
  attachments: PendingAttachment[],
): SendBlockReason {
  if (canSendMessage(content, attachments)) {
    return null;
  }
  if (hasUploadingAttachment(attachments)) {
    return "uploading";
  }
  if (attachments.some((item) => item.error)) {
    return "upload_failed";
  }
  return "empty";
}

export function buildSendPayload(
  content: string,
  attachments: PendingAttachment[],
): { content: string; attachment_file_ids: string[] } {
  const ids = attachments
    .filter(isAttachmentReady)
    .map((item) => item.uploaded?.file_id)
    .filter((id): id is string => Boolean(id));
  const text = content.trim();
  return {
    content: text || (ids.length > 0 ? ATTACHMENT_ONLY_INSTRUCTION : ""),
    attachment_file_ids: ids,
  };
}

export function formatAssistantContent(content: string): string {
  return content.replace(/\*\*(.+?)\*\*/g, "$1");
}

export function handleComposerKeyDown(
  event: { key: string; shiftKey: boolean; preventDefault: () => void },
  onSend: () => void,
): void {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    onSend();
  }
}

export function formatChatError(error: unknown): string {
  if (!(error instanceof Error)) {
    return "Something went wrong. Please try again.";
  }
  const message = error.message.trim();
  const lower = message.toLowerCase();
  if (!message) {
    return "Something went wrong. Please try again.";
  }
  if (lower.includes("401") || lower.includes("authentication") || lower.includes("sign in")) {
    return "Your session has expired. Please sign in again.";
  }
  if (lower.includes("403") || lower.includes("forbidden") || lower.includes("not authorized")) {
    return "You do not have access to this project or action.";
  }
  if (lower.includes("404") || lower.includes("not found")) {
    return "The requested engineering resource was not found.";
  }
  if (lower.includes("422")) {
    return "The request could not be processed. Check the inputs and try again.";
  }
  if (lower.includes("500") || lower.includes("internal server")) {
    return "The engineering service encountered an error. Please try again.";
  }
  if (lower.includes("failed to fetch") || lower.includes("network")) {
    return "The engineering service is temporarily unavailable.";
  }
  if (lower.includes("traceback") || lower.includes("syntaxerror")) {
    return "Something went wrong. Please try again.";
  }
  return message;
}

export function pendingChatApprovalId(
  result: {
    requiresApproval: boolean;
    approvalRequestId: string | null;
    executionStatus: string | null;
  } | null,
): string | null {
  if (!result?.requiresApproval || !result.approvalRequestId) {
    return null;
  }
  if (
    result.executionStatus &&
    result.executionStatus !== "awaiting_approval" &&
    result.executionStatus !== "in_progress"
  ) {
    return null;
  }
  return result.approvalRequestId;
}

export function workspaceActionsForChat(
  actions: Array<{ label: string; href: string }>,
  hasInlineApproval: boolean,
): Array<{ label: string; href: string }> {
  if (!hasInlineApproval) {
    return actions;
  }
  return actions.filter((action) => action.label !== "Review approval");
}

export function shouldShowEngineeringDisclaimer(content: string): boolean {
  const lower = content.toLowerCase();
  return (
    lower.includes("completed") ||
    lower.includes("analysis") ||
    lower.includes("design") ||
    lower.includes("validation")
  );
}
