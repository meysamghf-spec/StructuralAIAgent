"use client";

import Link from "next/link";
import { useDrawerDismiss } from "@/hooks/useDrawerDismiss";
import { useMemo, useState } from "react";

import { MainNav } from "@/components/MainNav";
import { SaiaLogo } from "@/components/brand/SaiaLogo";
import { ProjectFileTree } from "@/components/chat/ProjectFileTree";
import { NewProjectDialog } from "@/components/project/NewProjectDialog";
import { ProjectSwitcher } from "@/components/project/ProjectSwitcher";
import { useUiLang } from "@/hooks/useUiLang";
import type { ProjectSummary } from "@/lib/api";
import type { ProjectFileSummary } from "@/lib/api";
import type { ChatConversation } from "@/lib/chat-api";
import { filterConversations } from "@/lib/chat";

type ChatSidebarProps = {
  conversations: ChatConversation[];
  /** Older chats that never had a project; shown in a separate collapsed "General" list. */
  generalConversations?: ChatConversation[];
  projectScope?: {
    projects: ProjectSummary[];
    selectedProjectId: string;
    selectedProject: ProjectSummary | null;
    setSelectedProjectId: (id: string) => void;
  };
  activeConversationId: string | null;
  open: boolean;
  projectId?: string | null;
  projectName?: string | null;
  files?: ProjectFileSummary[];
  filesLoading?: boolean;
  filesError?: string | null;
  selectedFileId?: string | null;
  onSelectFile?: (file: ProjectFileSummary) => void;
  onRetryFiles?: () => void;
  onUploadFiles?: (files: FileList) => void;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConversation: (conversationId: string) => void;
  onDeleteConversation: (conversationId: string) => void;
  onRenameConversation?: (conversationId: string, title: string) => void;
  selectedProjectId?: string;
  userLabel: string;
  userEmail: string;
  onLogout: () => void;
};

export function ChatSidebar({
  conversations,
  generalConversations = [],
  projectScope,
  activeConversationId,
  open,
  projectId = null,
  projectName,
  files = [],
  filesLoading = false,
  filesError = null,
  selectedFileId = null,
  onSelectFile,
  onRetryFiles,
  onUploadFiles,
  onClose,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  onRenameConversation,
  selectedProjectId = "",
  userLabel,
  userEmail,
  onLogout,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const { t } = useUiLang();
  const [creating, setCreating] = useState(false);
  const [generalOpen, setGeneralOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  // The server already returns only the active project's chats; no client-side "all projects" view.
  const filteredConversations = useMemo(
    () => filterConversations(conversations, searchQuery),
    [conversations, searchQuery],
  );
  const filteredGeneral = useMemo(
    () => filterConversations(generalConversations, searchQuery),
    [generalConversations, searchQuery],
  );

  function commitRename(id: string) {
    const title = draftTitle.trim();
    setEditingId(null);
    if (title && onRenameConversation) {
      onRenameConversation(id, title);
    }
  }

  const renderConversation = (conversation: ChatConversation) => (
    <li key={conversation.id}>
      {editingId === conversation.id ? (
        <input
          className="input chat-conversation-rename"
          autoFocus
          aria-label="Rename conversation"
          dir="auto"
          value={draftTitle}
          maxLength={120}
          onChange={(event) => setDraftTitle(event.target.value)}
          onBlur={() => commitRename(conversation.id)}
          onKeyDown={(event) => {
            if (event.key === "Enter") commitRename(conversation.id);
            if (event.key === "Escape") setEditingId(null);
          }}
        />
      ) : (
        <button
          type="button"
          dir="auto"
          className={
            conversation.id === activeConversationId
              ? "chat-conversation-item active"
              : "chat-conversation-item"
          }
          onClick={() => onSelectConversation(conversation.id)}
          onDoubleClick={() => {
            if (onRenameConversation) {
              setDraftTitle(conversation.title);
              setEditingId(conversation.id);
            }
          }}
        >
          {conversation.title}
        </button>
      )}
      {onRenameConversation && editingId !== conversation.id ? (
        <button
          type="button"
          className="chat-conversation-rename-button"
          aria-label="Rename conversation"
          onClick={() => {
            setDraftTitle(conversation.title);
            setEditingId(conversation.id);
          }}
        >
          ✎
        </button>
      ) : null}
      <button
        type="button"
        className="chat-conversation-delete"
        aria-label="Delete conversation"
        onClick={() => onDeleteConversation(conversation.id)}
      >
        ×
      </button>
    </li>
  );

  const swipe = useDrawerDismiss(open, onClose);

  return (
    <>
      <button
        type="button"
        className="chat-sidebar-backdrop"
        aria-label="Close menu"
        data-open={open}
        onClick={onClose}
        {...swipe}
        data-testid="chat-backdrop"
      />
      <aside className="chat-sidebar" data-open={open} data-testid="chat-drawer" {...swipe}>
        <div className="chat-sidebar-header">
          <button type="button" className="drawer-close" aria-label="Close menu" data-testid="drawer-close" onClick={onClose}>✕</button>
          <Link href="/" className="brand-link" aria-label="SAIA home"><SaiaLogo size="md" /></Link>
          <h1>Engineering Chat</h1>
          <button className="button chat-new-button" type="button" data-testid="new-project-button" onClick={() => setCreating(true)}>
            <span aria-hidden="true">+</span> {t("New project")}
          </button>
        </div>
        <NewProjectDialog open={creating} onClose={() => setCreating(false)} onCreated={onClose} />

        <MainNav onNavigate={onClose} />

        <section className="chat-sidebar-section" aria-label="Project">
          <p className="chat-sidebar-label">{t("Project")}</p>
          {projectScope ? (
            <ProjectSwitcher variant="panel" scope={projectScope} onChange={onClose} />
          ) : (
            <p className="chat-sidebar-project-name">{projectName ?? t("No project selected")}</p>
          )}
          <ProjectFileTree
            projectId={projectId}
            files={files}
            loading={filesLoading}
            error={filesError}
            selectedFileId={selectedFileId}
            onSelectFile={(file) => {
              onSelectFile?.(file);
              onClose();
            }}
            onRetry={() => onRetryFiles?.()}
            onUpload={onUploadFiles}
          />
        </section>

        <nav className="chat-sidebar-section">
          <label className="chat-sidebar-search">
            <span className="chat-sidebar-label">Search conversations</span>
            <input
              className="input chat-search-input"
              type="search"
              placeholder="Search…"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </label>
          <div className="chat-history-head">
            <p className="chat-sidebar-label" data-testid="chat-history-label">
              {selectedProjectId ? t("Chat history of this project") : t("Recent conversations")}
            </p>
            {selectedProjectId ? (
              <button type="button" className="chat-history-new" data-testid="new-chat-in-project" onClick={onNewChat}>
                <span aria-hidden="true">+</span> {t("New chat")}
              </button>
            ) : null}
          </div>
          <ul className="chat-conversation-list">
            {filteredConversations.length === 0 ? (
              <li className="muted chat-empty">
                {searchQuery.trim() ? t("No matching conversations") : t("No chats in this project yet")}
              </li>
            ) : (
              filteredConversations.map(renderConversation)
            )}
          </ul>
          {selectedProjectId && filteredGeneral.length > 0 ? (
            <div className="chat-general" data-testid="chat-general">
              <button
                type="button"
                className="chat-general-toggle"
                aria-expanded={generalOpen}
                onClick={() => setGeneralOpen((v) => !v)}
              >
                {generalOpen ? "▾" : "▸"} {t("General (no project)")} ({filteredGeneral.length})
              </button>
              {generalOpen ? <ul className="chat-conversation-list">{filteredGeneral.map(renderConversation)}</ul> : null}
            </div>
          ) : null}
        </nav>


        <div className="chat-sidebar-footer">
          <p className="sidebar-auth-label">Account</p>
          <p className="sidebar-auth-user">{userLabel}</p>
          <p className="muted sidebar-auth-email">{userEmail}</p>
          <button className="button secondary sidebar-logout" type="button" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
