"use client";

import { AttachmentChip } from "./AttachmentChip";
import type { PendingAttachment } from "@/lib/chat";
import { canSendMessage, handleComposerKeyDown, sendBlockReason } from "@/lib/chat";
import { AGENT_CHAT_MODES, ENGINEERING_FILE_ACCEPT, type AgentChatMode } from "@/lib/chat-types";
import { FormEvent, useEffect, useRef, useState, type RefObject } from "react";

type ChatComposerProps = {
  content: string;
  attachments: PendingAttachment[];
  busy: boolean;
  projectSelected: boolean;
  mode?: AgentChatMode;
  variant?: "default" | "prominent";
  hintId?: string;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
  onContentChange: (value: string) => void;
  onModeChange?: (mode: AgentChatMode) => void;
  onSend: () => void;
  onStop?: () => void;
  onPickFiles: (files: FileList | File[]) => void;
  onRemoveAttachment: (localId: string) => void;
};

export function ChatComposer({
  content,
  attachments,
  busy,
  projectSelected,
  mode = "auto",
  variant = "default",
  hintId,
  inputRef,
  onContentChange,
  onModeChange,
  onSend,
  onStop,
  onPickFiles,
  onRemoveAttachment,
}: ChatComposerProps) {
  const localInputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = inputRef ?? localInputRef;
  const [dragActive, setDragActive] = useState(false);
  useEffect(() => {
    // Auto-growing composer: grow with content up to ~8 lines, then scroll.
    const el = textareaRef.current;
    if (!el) {
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [content, textareaRef]);
  const resolvedHintId = hintId ?? "chat-composer-hint";

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSendMessage(content, attachments) || busy) {
      return;
    }
    onSend();
  }

  function handleDrop(event: React.DragEvent<HTMLFormElement>) {
    event.preventDefault();
    if (event.dataTransfer.files.length > 0) {
      onPickFiles(event.dataTransfer.files);
    }
  }

  const isProminent = variant === "prominent";
  const blockReason = sendBlockReason(content, attachments);
  const uploading = blockReason === "uploading";
  const blockMessage =
    blockReason === "uploading"
      ? "Uploading file… Send will be enabled in a moment."
      : blockReason === "upload_failed"
        ? "Upload failed. Remove the file and try again, or type a message to send without it."
        : null;

  return (
    <form
      className={
        isProminent
          ? dragActive
            ? "chat-composer chat-composer-prominent chat-composer-drag-active"
            : "chat-composer chat-composer-prominent"
          : dragActive
            ? "chat-composer chat-composer-drag-active"
            : "chat-composer"
      }
      onSubmit={handleSubmit}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragActive(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={(event) => {
        if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
          return;
        }
        setDragActive(false);
      }}
      onDrop={(event) => {
        setDragActive(false);
        handleDrop(event);
      }}
      aria-busy={busy}
    >
      {attachments.length > 0 ? (
        <div className="chat-composer-attachments">
          {attachments.map((attachment) => (
            <AttachmentChip
              key={attachment.localId}
              attachment={attachment}
              onRemove={busy ? undefined : () => onRemoveAttachment(attachment.localId)}
            />
          ))}
        </div>
      ) : null}

      <div className="chat-composer-box">
        <textarea
          ref={textareaRef}
          className="input chat-composer-input"
          rows={isProminent ? 3 : 1}
          placeholder={
            isProminent
              ? "Tell SAIA what you want to accomplish…"
              : "Ask SAIA…"
          }
          value={content}
          onChange={(event) => onContentChange(event.target.value)}
          onKeyDown={(event) => {
            if (!canSendMessage(content, attachments) || busy) {
              return;
            }
            handleComposerKeyDown(event, onSend);
          }}
          disabled={busy}
          aria-label="Type your structural engineering request"
          aria-describedby={resolvedHintId}
          aria-disabled={busy}
        />
        <div className="chat-composer-toolbar">
          <input
            ref={fileInputRef}
            type="file"
            className="chat-file-input"
            multiple
            accept={ENGINEERING_FILE_ACCEPT}
            disabled={busy}
            onChange={(event) => {
              if (event.target.files) {
                onPickFiles(event.target.files);
                event.target.value = "";
              }
            }}
          />
          <button
            type="button"
            className="button secondary chat-composer-icon-button"
            disabled={busy}
            aria-label="Attach engineering file"
            onClick={() => fileInputRef.current?.click()}
          >
            {isProminent ? "Attach file" : "Attach"}
          </button>
          <label className="chat-mode-select">
            <span className="visually-hidden">Agent mode</span>
            <select
              className="input chat-mode-input"
              value={mode}
              disabled={busy}
              aria-label="Agent mode"
              onChange={(event) => onModeChange?.(event.target.value as AgentChatMode)}
            >
              {AGENT_CHAT_MODES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          {busy && onStop ? (
            <button
              className="button chat-composer-send chat-composer-stop"
              type="button"
              onClick={onStop}
              aria-label="Stop generating"
              data-testid="chat-stop"
            >
              ■ Stop
            </button>
          ) : null}
          <button
            className="button chat-composer-send"
            hidden={Boolean(busy && onStop)}
            type="submit"
            disabled={busy || !canSendMessage(content, attachments)}
            aria-label={busy ? "Sending message" : "Send message"}
            aria-disabled={busy || !canSendMessage(content, attachments)}
            data-testid="chat-send"
          >
            {uploading ? <span className="chat-spinner" aria-hidden="true" /> : null}
            {busy ? "Sending…" : uploading ? "Uploading…" : "Send"}
          </button>
        </div>
      </div>
      {blockMessage ? (
        <p
          className={blockReason === "upload_failed" ? "chat-composer-status error" : "chat-composer-status"}
          role="status"
          aria-live="polite"
          data-testid="chat-send-status"
        >
          {blockMessage}
        </p>
      ) : null}
      {!isProminent ? (
        <p id={resolvedHintId} className="muted chat-composer-hint">
          Enter to send · Shift+Enter for a new line · Drag and drop supported engineering files
          {!projectSelected ? " · Select a project before attaching files" : ""}
        </p>
      ) : (
        <p
          id={resolvedHintId}
          className="muted chat-composer-hint chat-composer-hint-prominent"
        >
          Enter to send · Shift+Enter for a new line · Attach supported engineering files
          {!projectSelected ? " · Select a project before attaching files" : ""}
        </p>
      )}
    </form>
  );
}
