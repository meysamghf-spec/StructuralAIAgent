import {
  isTerminalAgentRunEvent,
  parseSseBlock,
  type AgentRunSseEvent,
} from "./agent-run-sse";
import { getApiBaseUrl } from "./api";
import { getAuthHeaders, getUploadAuthHeaders } from "./auth-session";

export type ChatAttachment = {
  file_id: string;
  filename: string;
  file_type: string | null;
  content_type: string | null;
  status: string;
  parsing_status: string | null;
  extraction_status: string | null;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  attachments: ChatAttachment[];
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ChatConversation = {
  id: string;
  account_id: string;
  project_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatAction = {
  label: string;
  href: string;
};

async function chatFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...getAuthHeaders(),
    ...(init?.headers ? Object.fromEntries(new Headers(init.headers).entries()) : {}),
  };
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Request failed (${response.status})`;
    throw new Error(message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function listConversations(): Promise<ChatConversation[]> {
  const response = await chatFetch<{ conversations: ChatConversation[] }>("/api/v1/conversations");
  return response.conversations;
}

export async function createConversation(input: {
  title?: string;
  project_id?: string;
}): Promise<ChatConversation> {
  return chatFetch<ChatConversation>("/api/v1/conversations", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getConversation(conversationId: string): Promise<ChatConversation> {
  return chatFetch<ChatConversation>(`/api/v1/conversations/${conversationId}`);
}

export async function renameConversation(conversationId: string, title: string): Promise<ChatConversation> {
  return chatFetch<ChatConversation>(`/api/v1/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await chatFetch<void>(`/api/v1/conversations/${conversationId}`, { method: "DELETE" });
}

export async function listConversationMessages(conversationId: string): Promise<ChatMessage[]> {
  const response = await chatFetch<{ messages: ChatMessage[] }>(
    `/api/v1/conversations/${conversationId}/messages`,
  );
  return response.messages;
}

export type ChatSendResponse = {
  conversation_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  execution_status: string | null;
  selected_capability: string | null;
  artifacts: Array<{
    id: string;
    name: string;
    artifact_type: string;
    description: string | null;
    href: string | null;
  }>;
  status_events: string[];
};

export async function sendChatMessage(input: {
  message: string;
  conversation_id?: string;
  project_id?: string;
  attachments?: string[];
  mode?: string;
  assistant?: string;
}): Promise<ChatSendResponse> {
  return chatFetch("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

function asChatMessage(raw: unknown): ChatMessage | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const data = raw as Record<string, unknown>;
  if (typeof data.id !== "string" || typeof data.conversation_id !== "string" || typeof data.role !== "string") {
    return null;
  }
  return {
    id: data.id,
    conversation_id: data.conversation_id,
    role: data.role as ChatMessage["role"],
    content: typeof data.content === "string" ? data.content : "",
    attachments: Array.isArray(data.attachments) ? (data.attachments as ChatMessage["attachments"]) : [],
    metadata: data.metadata && typeof data.metadata === "object" ? (data.metadata as Record<string, unknown>) : {},
    created_at: typeof data.created_at === "string" ? data.created_at : new Date().toISOString(),
  };
}

const STREAM_IDLE_MS = 90_000;

function readWithTimeout(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  ms: number,
): Promise<ReadableStreamReadResult<Uint8Array>> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      void reader.cancel().catch(() => undefined);
      reject(new Error("The agent stream stopped responding."));
    }, ms);
  });
  return Promise.race([reader.read(), timeout]).finally(() => clearTimeout(timer));
}

export async function streamChatMessage(
  input: {
    message: string;
    conversation_id?: string;
    project_id?: string;
    attachments?: string[];
    mode?: string;
    assistant?: string;
  },
  options: {
    onEvent: (event: AgentRunSseEvent) => void;
    signal?: AbortSignal;
  },
): Promise<ChatSendResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(input),
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Request failed (${response.status})`;
    throw new Error(message);
  }
  if (!response.body) {
    throw new Error("Streaming is not available.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let conversationId = input.conversation_id ?? "";
  let userMessage: ChatMessage | null = null;
  let assistantMessage: ChatMessage | null = null;

  try {
    while (true) {
      // Watchdog: a dropped mobile connection can leave read() pending forever, which kept the
      // composer disabled (busy) after the first message. Give up after STREAM_IDLE_MS of silence.
      const { done, value } = await readWithTimeout(reader, STREAM_IDLE_MS);
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (!event) {
          continue;
        }
        options.onEvent(event);
        if (typeof event.data.conversation_id === "string") {
          conversationId = event.data.conversation_id;
        }
        const nextUser = asChatMessage(event.data.user_message);
        if (nextUser) {
          userMessage = nextUser;
        }
        const nextAssistant = asChatMessage(event.data.assistant_message);
        if (nextAssistant) {
          assistantMessage = nextAssistant;
        }
        if (isTerminalAgentRunEvent(event.type, event.data) && userMessage && assistantMessage) {
          void reader.cancel().catch(() => undefined);
          return {
            conversation_id: conversationId || assistantMessage.conversation_id,
            user_message: userMessage,
            assistant_message: assistantMessage,
            execution_status: null,
            selected_capability: null,
            artifacts: [],
            status_events: [],
          };
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // lock already released by cancel()
    }
  }

  if (!userMessage || !assistantMessage) {
    throw new Error("The agent stream ended before a complete response was received.");
  }
  return {
    conversation_id: conversationId || assistantMessage.conversation_id,
    user_message: userMessage,
    assistant_message: assistantMessage,
    execution_status: null,
    selected_capability: null,
    artifacts: [],
    status_events: [],
  };
}

export async function sendConversationMessage(
  conversationId: string,
  input: { content: string; attachment_file_ids?: string[] },
): Promise<{ user_message: ChatMessage; assistant_message: ChatMessage }> {
  return chatFetch(`/api/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function uploadConversationAttachment(
  conversationId: string,
  file: File,
  projectId?: string,
): Promise<{ attachment: ChatAttachment; project_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/conversations/${conversationId}/attachments${query}`,
    {
      method: "POST",
      headers: getUploadAuthHeaders(),
      body: formData,
      cache: "no-store",
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Upload failed (${response.status})`;
    throw new Error(message);
  }
  return response.json();
}
