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
  | { type: "heading"; text: string }
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

export function parseMessageContent(content: string): MessageBlock[] {
  return content.split("\n").map((line) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("### ")) {
      return { type: "heading", text: trimmed.slice(4) };
    }
    if (trimmed.startsWith("- ")) {
      return { type: "list-item", text: trimmed.slice(2) };
    }
    return { type: "paragraph", text: line };
  });
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
  return `optimistic-${crypto.randomUUID()}`;
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

export function canSendMessage(content: string, attachments: PendingAttachment[]): boolean {
  const hasText = content.trim().length > 0;
  const hasReadyFiles = attachments.some((item) => item.uploaded && !item.error);
  const isUploading = attachments.some((item) => item.uploading);
  return (hasText || hasReadyFiles) && !isUploading;
}

export function buildSendPayload(
  content: string,
  attachments: PendingAttachment[],
): { content: string; attachment_file_ids: string[] } {
  return {
    content: content.trim(),
    attachment_file_ids: attachments
      .map((item) => item.uploaded?.file_id)
      .filter((id): id is string => Boolean(id)),
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
