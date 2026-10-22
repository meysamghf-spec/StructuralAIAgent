"use client";

import Link from "next/link";
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
  userLabel,
  userEmail,
  onLogout,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const filteredConversations = useMemo(
    () => filterConversations(conversations, searchQuery),
    [conversations, searchQuery],
  );

  return (
    <>
      <button
        type="button"
        className="chat-sidebar-backdrop"
        aria-label="Close menu"
        data-open={open}
        onClick={onClose}
      />
      <aside className="chat-sidebar" data-open={open}>
        <div className="chat-sidebar-header">
          <p className="brand-eyebrow">StructuralAIAgent</p>
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
          <ul className="chat-conversation-list">
            {filteredConversations.length === 0 ? (
              <li className="muted chat-empty">
                {searchQuery.trim() ? "No matching conversations" : "No conversations yet"}
              </li>
            ) : (
              filteredConversations.map((conversation) => (
                <li key={conversation.id}>
                  <button
                    type="button"
                    className={
                      conversation.id === activeConversationId
                        ? "chat-conversation-item active"
                        : "chat-conversation-item"
                    }
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    {conversation.title}
                  </button>
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
