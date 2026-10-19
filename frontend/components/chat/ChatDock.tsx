"use client";

import { useRef, useState } from "react";

import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatThread } from "@/components/chat/ChatThread";
import { useAuth } from "@/hooks/useAuth";
import { useChat } from "@/hooks/useChat";
import { useProjectScope } from "@/hooks/useProjectScope";
import { useUiLang } from "@/hooks/useUiLang";

/** Collapsible right-side project chat available on every workspace/projects page (same thread + result cards as /). */
export function ChatDock() {
  const [open, setOpen] = useState(false);
  return (
    <>
      {!open ? <DockToggle onClick={() => setOpen(true)} /> : null}
      {open ? <DockPanel onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function DockToggle({ onClick }: { onClick: () => void }) {
  const { t } = useUiLang();
  return (
    <button type="button" className="chat-dock-toggle" onClick={onClick} aria-label={t("Open chat")}>
      💬 {t("Chat")}
    </button>
  );
}

function DockPanel({ onClose }: { onClose: () => void }) {
  const { t, lang } = useUiLang();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { projects, selectedProjectId, setSelectedProjectId, selectedProject } = useProjectScope();
  const chat = useChat({ isAuthenticated, authLoading, selectedProjectId, setSelectedProjectId });
  return (
    <aside className="chat-dock" aria-label={t("Project chat")} dir={lang === "fa" ? "rtl" : "ltr"}>
      <header className="chat-dock-header">
        <strong>{t("Project chat")}</strong>
        <select
          value={selectedProjectId ?? ""}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          aria-label={t("Project")}
        >
          {projects.length === 0 ? <option value="">{t("No project selected")}</option> : null}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button type="button" className="button secondary" onClick={onClose} aria-label={t("Close chat")}>
          ✕
        </button>
      </header>
      {chat.error ? <div className="alert error">{chat.error}</div> : null}
      <div className="chat-dock-body">
        <ChatThread
          messages={chat.messages}
          busy={chat.busy}
          loadingMessages={chat.loadingMessages}
          executionPhase={chat.executionPhase}
          statusLabel={chat.statusLabel}
          projectId={selectedProjectId || null}
          projectName={selectedProject?.name ?? null}
          onApprovalResolved={() => void chat.handleApprovalResolved()}
        />
      </div>
      <ChatComposer
        variant="default"
        content={chat.content}
        attachments={chat.pendingAttachments}
        busy={chat.busy}
        projectSelected={Boolean(selectedProjectId)}
        mode={chat.mode}
        inputRef={inputRef}
        onContentChange={chat.setContent}
        onModeChange={chat.setMode}
        onSend={() => void chat.handleSend()}
        onPickFiles={(files: FileList | File[]) => void chat.handlePickFiles(files)}
        onRemoveAttachment={chat.removeAttachment}
      />
    </aside>
  );
}
