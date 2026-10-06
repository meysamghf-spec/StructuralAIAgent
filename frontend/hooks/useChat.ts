"use client";

import { agentRunToMetadata, applyAgentRunEvent } from "@/lib/agent-run-sse";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversationMessages,
  listConversations,
  sendChatMessage,
  streamChatMessage,
  uploadConversationAttachment,
  type ChatConversation,
  type ChatMessage,
} from "@/lib/chat-api";
import {
  buildOptimisticAssistantMessage,
  buildOptimisticUserMessage,
  buildSendPayload,
  canSendMessage,
  createOptimisticMessageId,
  formatChatError,
  getStoredActiveConversationId,
  optimisticAssistantId,
  replaceOptimisticMessages,
  storeActiveConversationId,
  type PendingAttachment,
  type PendingSendRequest,
} from "@/lib/chat";
import { attachExistingProjectFile } from "@/lib/project-files";
import type { ProjectFileSummary } from "@/lib/api";
import { STREAMING_CAPABILITIES, type AgentChatMode, type ExecutionPhase } from "@/lib/chat-types";
import { mapBackendMessage } from "@/lib/chat-mappers";
import { useCallback, useEffect, useMemo, useState } from "react";

type UseChatOptions = {
  isAuthenticated: boolean;
  authLoading: boolean;
  selectedProjectId: string;
  setSelectedProjectId: (projectId: string) => void;
};

export function useChat({
  isAuthenticated,
  authLoading,
  selectedProjectId,
  setSelectedProjectId,
}: UseChatOptions) {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [content, setContent] = useState("");
  const [mode, setMode] = useState<AgentChatMode>("auto");
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [busy, setBusy] = useState(false);
  const [executionPhase, setExecutionPhase] = useState<ExecutionPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [retryRequest, setRetryRequest] = useState<PendingSendRequest | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const statusLabel = useMemo(() => {
    if (executionPhase === "uploading") {
      return "Uploading files…";
    }
    if (executionPhase === "building_context") {
      return "Building engineering context…";
    }
    if (executionPhase === "processing") {
      return "Running engineering workflow…";
    }
    return null;
  }, [executionPhase]);

  const refreshConversations = useCallback(async () => {
    const items = await listConversations();
    setConversations(items);
    return items;
  }, []);

  const loadMessages = useCallback(async (conversationId: string) => {
    setLoadingMessages(true);
    try {
      const items = await listConversationMessages(conversationId);
      setMessages(items);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated || authLoading) {
      setBootstrapping(false);
      return;
    }
    let active = true;
    async function bootstrap() {
      try {
        const items = await refreshConversations();
        const storedId = getStoredActiveConversationId();
        const initialId =
          storedId && items.some((item) => item.id === storedId) ? storedId : items[0]?.id ?? null;
        if (!active) {
          return;
        }
        setActiveConversationId(initialId);
        if (initialId) {
          await loadMessages(initialId);
          const conversation = await getConversation(initialId);
          if (conversation.project_id) {
            setSelectedProjectId(conversation.project_id);
          }
        }
      } catch (err) {
        if (active) {
          setError(formatChatError(err));
        }
      } finally {
        if (active) {
          setBootstrapping(false);
        }
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, [authLoading, isAuthenticated, loadMessages, refreshConversations, setSelectedProjectId]);

  async function ensureConversation(): Promise<string> {
    if (activeConversationId) {
      return activeConversationId;
    }
    const conversation = await createConversation({
      title: "New conversation",
      project_id: selectedProjectId || undefined,
    });
    setConversations((current) => [conversation, ...current]);
    setActiveConversationId(conversation.id);
    storeActiveConversationId(conversation.id);
    return conversation.id;
  }

  async function submitChatRequest(request: PendingSendRequest, options: { isRetry: boolean }) {
    setBusy(true);
    setExecutionPhase("building_context");
    try {
      setExecutionPhase("processing");
      const payload = {
        message: request.message,
        conversation_id: request.conversation_id,
        project_id: request.project_id,
        attachments: request.attachments,
        mode: request.mode ?? mode,
      };
      const assistantOptimisticId = optimisticAssistantId(request.optimisticMessageId);
      let response;
      if (STREAMING_CAPABILITIES.supported) {
        try {
          response = await streamChatMessage(payload, {
            onEvent: (event) => {
              setMessages((current) =>
                current.map((message) => {
                  if (message.id !== assistantOptimisticId) {
                    return message;
                  }
                  const currentRun = mapBackendMessage(message).engineeringResult?.agentRun ?? null;
                  return {
                    ...message,
                    metadata: {
                      ...message.metadata,
                      mode: "agent_execution",
                      streaming: true,
                      agent_run: agentRunToMetadata(applyAgentRunEvent(currentRun, event)),
                    },
                  };
                }),
              );
            },
          });
        } catch (streamError) {
          response = await sendChatMessage(payload);
          void streamError;
        }
      } else {
        response = await sendChatMessage(payload);
      }
      setActiveConversationId(response.conversation_id);
      storeActiveConversationId(response.conversation_id);
      setMessages((current) =>
        replaceOptimisticMessages(
          current,
          request.optimisticMessageId,
          response.user_message,
          response.assistant_message,
        ),
      );
      setRetryRequest(null);
      await refreshConversations();
    } catch (err) {
      setExecutionPhase("error");
      setError(formatChatError(err));
      setRetryRequest(request);
    } finally {
      setBusy(false);
      setExecutionPhase("idle");
    }
  }

  async function handleSend() {
    if (busy) {
      return;
    }
    if (!canSendMessage(content, pendingAttachments)) {
      return;
    }

    setError(null);
    const payload = buildSendPayload(content, pendingAttachments);
    const optimisticId = createOptimisticMessageId();
    const attachmentSnapshot = pendingAttachments.map((item) => ({ ...item }));
    const conversationId = activeConversationId ?? "pending";

    setMessages((current) => [
      ...current,
      buildOptimisticUserMessage(
        optimisticId,
        conversationId,
        payload.content,
        pendingAttachments,
      ),
      buildOptimisticAssistantMessage(optimisticId, conversationId),
    ]);
    setContent("");
    setPendingAttachments([]);

    const request: PendingSendRequest = {
      message: payload.content,
      conversation_id: activeConversationId ?? undefined,
      project_id: selectedProjectId || undefined,
      attachments: payload.attachment_file_ids,
      mode,
      optimisticMessageId: optimisticId,
      pendingAttachments: attachmentSnapshot,
    };

    await submitChatRequest(request, { isRetry: false });
  }

  async function handleRetry() {
    if (busy || !retryRequest) {
      return;
    }
    setError(null);
    await submitChatRequest(retryRequest, { isRetry: true });
  }

  function handleDismissError() {
    setError(null);
    if (!retryRequest) {
      return;
    }
    setMessages((current) =>
      current.filter(
        (message) =>
          message.id !== retryRequest.optimisticMessageId &&
          message.id !== optimisticAssistantId(retryRequest.optimisticMessageId),
      ),
    );
    setContent(retryRequest.message);
    setPendingAttachments(retryRequest.pendingAttachments);
    setRetryRequest(null);
  }

  async function handleNewChat() {
    setError(null);
    setRetryRequest(null);
    setSidebarOpen(false);
    try {
      const conversation = await createConversation({
        title: "New conversation",
        project_id: selectedProjectId || undefined,
      });
      setConversations((current) => [conversation, ...current]);
      setActiveConversationId(conversation.id);
      storeActiveConversationId(conversation.id);
      setMessages([]);
      setContent("");
      setPendingAttachments([]);
    } catch (err) {
      setError(formatChatError(err));
    }
  }

  async function handleSelectConversation(conversationId: string) {
    setError(null);
    setRetryRequest(null);
    setSidebarOpen(false);
    setActiveConversationId(conversationId);
    storeActiveConversationId(conversationId);
    setPendingAttachments([]);
    try {
      await loadMessages(conversationId);
      const conversation = await getConversation(conversationId);
      if (conversation.project_id) {
        setSelectedProjectId(conversation.project_id);
      }
    } catch (err) {
      setError(formatChatError(err));
    }
  }

  async function handleDeleteConversation(conversationId: string) {
    setError(null);
    try {
      await deleteConversation(conversationId);
      const remaining = conversations.filter((item) => item.id !== conversationId);
      setConversations(remaining);
      if (activeConversationId === conversationId) {
        const nextId = remaining[0]?.id ?? null;
        setActiveConversationId(nextId);
        storeActiveConversationId(nextId);
        setMessages([]);
        setRetryRequest(null);
        if (nextId) {
          await loadMessages(nextId);
        }
      }
    } catch (err) {
      setError(formatChatError(err));
    }
  }

  async function handlePickFiles(files: FileList | File[]) {
    setError(null);
    const list = Array.from(files);
    if (list.length === 0) {
      return;
    }
    if (!selectedProjectId) {
      setError("Select a project before attaching engineering files.");
      return;
    }

    setExecutionPhase("uploading");
    const conversationId = await ensureConversation();
    const queued = list.map((file) => ({
      localId: crypto.randomUUID(),
      file,
      uploading: true,
    }));
    setPendingAttachments((current) => [...current, ...queued]);

    try {
      for (const item of queued) {
        try {
          if (!item.file) {
            continue;
          }
          const response = await uploadConversationAttachment(
            conversationId,
            item.file,
            selectedProjectId,
          );
          setPendingAttachments((current) =>
            current.map((entry) =>
              entry.localId === item.localId
                ? { ...entry, uploading: false, uploaded: response.attachment }
                : entry,
            ),
          );
        } catch (err) {
          setPendingAttachments((current) =>
            current.map((entry) =>
              entry.localId === item.localId
                ? {
                    ...entry,
                    uploading: false,
                    error: formatChatError(err),
                  }
                : entry,
            ),
          );
        }
      }
    } finally {
      setExecutionPhase("idle");
    }
  }

  return {
    conversations,
    activeConversationId,
    messages,
    content,
    setContent,
    mode,
    setMode,
    pendingAttachments,
    busy,
    loadingMessages,
    executionPhase,
    statusLabel,
    error,
    setError,
    retryRequest,
    bootstrapping,
    sidebarOpen,
    setSidebarOpen,
    handleNewChat,
    handleSelectConversation,
    handleDeleteConversation,
    handlePickFiles,
    handleSend,
    handleRetry,
    handleDismissError,
    handleApprovalResolved: async () => {
      if (!activeConversationId) {
        return;
      }
      try {
        await loadMessages(activeConversationId);
        await refreshConversations();
      } catch (err) {
        setError(formatChatError(err));
      }
    },
    removeAttachment: (localId: string) =>
      setPendingAttachments((current) => current.filter((item) => item.localId !== localId)),
    attachExistingProjectFile: (file: ProjectFileSummary) => {
      setPendingAttachments((current) => attachExistingProjectFile(current, file));
    },
  };
}
