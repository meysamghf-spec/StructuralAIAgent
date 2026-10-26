"use client";

import Link from "next/link";
import { useDrawerDismiss } from "@/hooks/useDrawerDismiss";
import { useMemo, useState } from "react";

import { MainNav } from "@/components/MainNav";
import { ProjectFileTree } from "@/components/chat/ProjectFileTree";
import type { ProjectFileSummary } from "@/lib/api";
import type { ChatConversation } from "@/lib/chat-api";
import { filterConversations } from "@/lib/chat";

type ChatSidebarProps = {
  conversations: ChatConversation[];
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
  const [scopeAll, setScopeAll] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const scoped = useMemo(
    () =>
      selectedProjectId && !scopeAll
        ? conversations.filter((item) => item.project_id === selectedProjectId)
        : conversations,
    [conversations, selectedProjectId, scopeAll],
  );
  const filteredConversations = useMemo(
    () => filterConversations(scoped, searchQuery),
    [scoped, searchQuery],
  );

  function commitRename(id: string) {
    const title = draftTitle.trim();
    setEditingId(null);
    if (title && onRenameConversation) {
      onRenameConversation(id, title);
    }
  }

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
          <p className="brand-eyebrow">SAIA</p>
          <h1>Engineering Chat</h1>
          <button className="button chat-new-button" type="button" onClick={onNewChat}>
            + New Chat
          </button>
        </div>

        <MainNav onNavigate={onClose} />

        <section className="chat-sidebar-section" aria-label="Project">
          <p className="chat-sidebar-label">Project</p>
          <p className="chat-sidebar-project-name">{projectName ?? "No project selected"}</p>
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
          <p className="chat-sidebar-label">Recent conversations</p>
          {selectedProjectId ? (
            <div className="chat-scope-toggle" role="group" aria-label="Conversation scope">
              <button type="button" className={!scopeAll ? "active" : ""} onClick={() => setScopeAll(false)}>
                This project
              </button>
              <button type="button" className={scopeAll ? "active" : ""} onClick={() => setScopeAll(true)}>
                All
              </button>
            </div>
          ) : null}
          <ul className="chat-conversation-list">
            {filteredConversations.length === 0 ? (
              <li className="muted chat-empty">
                {searchQuery.trim() ? "No matching conversations" : "No conversations yet"}
              </li>
            ) : (
              filteredConversations.map((conversation) => (
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
              ))
            )}
          </ul>
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
