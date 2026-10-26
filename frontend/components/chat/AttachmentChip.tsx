"use client";



import type { ChatAttachment } from "@/lib/chat-api";

import type { PendingAttachment } from "@/lib/chat";

import { attachmentLimitationNote, attachmentStatusLabel } from "@/lib/chat";



type AttachmentChipProps = {

  attachment: ChatAttachment | PendingAttachment;

  onRemove?: () => void;

};



function resolveFilename(attachment: ChatAttachment | PendingAttachment): string {
  if ("uploaded" in attachment && attachment.uploaded) {
    return attachment.uploaded.filename;
  }
  if ("filename" in attachment) {
    return attachment.filename;
  }
  return attachment.file?.name ?? "file";
}

function resolveType(attachment: ChatAttachment | PendingAttachment): string {
  if ("uploaded" in attachment && attachment.uploaded?.file_type) {
    return attachment.uploaded.file_type;
  }
  if ("file_type" in attachment && attachment.file_type) {
    return attachment.file_type;
  }
  if ("file" in attachment && attachment.file) {
    return attachment.file.type || "file";
  }
  return "file";
}



function resolveLimitation(attachment: ChatAttachment | PendingAttachment): string | null {

  if ("uploaded" in attachment && attachment.uploaded) {

    return attachmentLimitationNote(attachment.uploaded);

  }

  if ("file_id" in attachment) {

    return attachmentLimitationNote(attachment);

  }

  return null;

}



export function AttachmentChip({ attachment, onRemove }: AttachmentChipProps) {

  const status = attachmentStatusLabel(attachment);

  const isReady = status === "Ready";

  const limitation = resolveLimitation(attachment);



  return (

    <div className="chat-attachment-chip">

      <div>

        <p className="chat-attachment-name">📎 {resolveFilename(attachment)}</p>

        <p className="muted chat-attachment-meta">

          {status === "Uploading…" ? <span className="chat-spinner small" aria-hidden="true" /> : null}
          {resolveType(attachment)} · {status}

        </p>

        {limitation ? <p className="chat-attachment-limitation">{limitation}</p> : null}

        {"error" in attachment && attachment.error ? (

          <p className="chat-attachment-limitation error">{attachment.error}</p>

        ) : null}

      </div>

      {onRemove ? (

        <button
          type="button"
          className="chat-attachment-remove"
          onClick={onRemove}
          aria-label={`Remove ${resolveFilename(attachment)}`}
        >

          Remove

        </button>

      ) : isReady ? (

        <span className="chat-attachment-ready">✓</span>

      ) : null}

    </div>

  );

}

