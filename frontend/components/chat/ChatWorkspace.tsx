"use client";

import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatContextPanel } from "@/components/chat/ChatContextPanel";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatThread } from "@/components/chat/ChatThread";
import { PromptExamples } from "@/components/chat/PromptExamples";
import { useAuth } from "@/hooks/useAuth";
import { useChat } from "@/hooks/useChat";
import { useProjectFiles } from "@/hooks/useProjectFiles";
import { useProjectScope } from "@/hooks/useProjectScope";
import { downloadProjectFile, uploadProjectFile, type ProjectFileSummary } from "@/lib/api";
import { shouldShowProminentPrompt, storeActiveConversationId } from "@/lib/chat";
import { mapBackendMessage } from "@/lib/chat-mappers";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

export default function ChatWorkspace() {
  const { user, isAuthenticated, loading: authLoading, logout } = useAuth();
  const router = useRouter();
  const composerInputRef = useRef<HTMLTextAreaElement>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<ProjectFileSummary | null>(null);
  const [filesRefreshToken, setFilesRefreshToken] = useState(0);
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    selectedProject,
    loading: projectsLoading,
  } = useProjectScope();

  const chat = useChat({
    isAuthenticated,
    authLoading,
    selectedProjectId,
    setSelectedProjectId,
  });
  const projectFiles = useProjectFiles(selectedProjectId || null, filesRefreshToken);

  useEffect(() => {
    setSelectedFile(null);
  }, [selectedProjectId]);

  const activeConversation = chat.conversations.find(
    (item) => item.id === chat.activeConversationId,
  );

  const latestEngineering = useMemo(() => {
    for (let index = chat.messages.length - 1; index >= 0; index -= 1) {
      const mapped = mapBackendMessage(chat.messages[index]);
      if (mapped.role === "assistant" && mapped.engineeringResult) {
        return mapped.engineeringResult;
      }
    }
    return null;
  }, [chat.messages]);

  const showProminentPrompt = shouldShowProminentPrompt({
    loadingMessages: chat.loadingMessages,
    messageCount: chat.messages.length,
    busy: chat.busy,
  });

  const hasStructuredContext = Boolean(
    latestEngineering?.agentRun ||
      latestEngineering?.demoResults ||
      latestEngineering?.aciBeamResults ||
      latestEngineering?.requiresApproval,
  );

  useEffect(() => {
    if (hasStructuredContext) {
      setContextOpen(true);
    }
  }, [
    hasStructuredContext,
    latestEngineering?.approvalRequestId,
    latestEngineering?.agentRun?.lifecycle,
    latestEngineering?.demoResults?.kind,
    latestEngineering?.aciBeamResults?.kind,
  ]);

  const composerProps = {
    content: chat.content,
    attachments: chat.pendingAttachments,
    busy: chat.busy,
    projectSelected: Boolean(selectedProjectId),
    mode: chat.mode,
    inputRef: composerInputRef,
    onContentChange: chat.setContent,
    onModeChange: chat.setMode,
    onSend: () => void chat.handleSend(),
    onPickFiles: (files: FileList | File[]) => {
      void chat.handlePickFiles(files).then(() => {
        setFilesRefreshToken((value) => value + 1);
      });
    },
    onRemoveAttachment: chat.removeAttachment,
  };

  function handleExampleSelect(text: string) {
    chat.setContent(text);
    requestAnimationFrame(() => {
      const input = composerInputRef.current;
      if (!input) {
        return;
      }
      input.focus();
      input.setSelectionRange(text.length, text.length);
    });
  }

  function handleLogout() {
    logout();
    storeActiveConversationId(null);
    router.replace("/login");
  }

  if (authLoading || chat.bootstrapping) {
    return (
      <div className="chat-loading">
        <p className="muted">Loading engineering chat…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <section className="panel-stack chat-guest">
        <header className="page-header">
          <p className="eyebrow">Structural Engineering AI</p>
          <h2>Chat-first structural engineering workspace</h2>
          <p className="subtitle">
            Tell the AI what you need, attach ETABS models, PDFs, drawings, and spreadsheets,
            and run engineering workflows from one conversation.
          </p>
        </header>
        <div className="card">
          <p>
            <Link href="/login">Sign in</Link> or <Link href="/register">create an account</Link>{" "}
            to start chatting with your project context, files, and engineering agents.
          </p>
        </div>
      </section>
    );
  }

  return (
    <div className="chat-shell" data-context-open={contextOpen ? "true" : "false"}>
      <ChatSidebar
        conversations={chat.conversations}
        activeConversationId={chat.activeConversationId}
        open={chat.sidebarOpen}
        projectId={selectedProjectId || null}
        projectName={selectedProject?.name ?? null}
        files={projectFiles.files}
        filesLoading={projectFiles.loading}
        filesError={projectFiles.error}
        selectedFileId={selectedFile?.id ?? null}
        onSelectFile={(file) => {
          setSelectedFile(file);
          setContextOpen(true);
        }}
        onRetryFiles={projectFiles.retry}
        onUploadFiles={(fileList) => {
          void (async () => {
            if (!selectedProjectId) {
              return;
            }
            try {
              for (const file of Array.from(fileList)) {
                await uploadProjectFile(selectedProjectId, file);
              }
              setFilesRefreshToken((value) => value + 1);
            } catch (err) {
              chat.setError(err instanceof Error ? err.message : "Upload failed.");
            }
          })();
        }}
        onClose={() => chat.setSidebarOpen(false)}
        onNewChat={() => void chat.handleNewChat()}
        onSelectConversation={(id) => void chat.handleSelectConversation(id)}
        onDeleteConversation={(id) => void chat.handleDeleteConversation(id)}
        userLabel={user?.display_name ?? user?.email ?? "User"}
        userEmail={user?.email ?? ""}
        onLogout={handleLogout}
      />

      <section className={showProminentPrompt ? "chat-main chat-main--welcome" : "chat-main"}>
        <header
          className={
            showProminentPrompt ? "chat-main-header chat-main-header-compact" : "chat-main-header"
          }
        >
          <div className="chat-main-header-left">
            <button
              type="button"
              className="button secondary chat-menu-button"
              onClick={() => chat.setSidebarOpen(true)}
              aria-label="Open conversation menu"
            >
              Menu
            </button>
            {!showProminentPrompt ? (
              <div>
                <p className="eyebrow">StructuralAIAgent</p>
                <h2>{activeConversation?.title ?? "New Chat"}</h2>
                {selectedProject ? (
                  <span className="chat-project-badge">Project: {selectedProject.name}</span>
                ) : (
                  <span className="chat-project-badge muted">
                    No project selected — required for file attachments
                  </span>
                )}
              </div>
            ) : (
              <p className="chat-main-header-title">StructuralAIAgent</p>
            )}
          </div>
          <label className="chat-project-select">
            <span className="chat-project-select-label">Project context</span>
            <select
              className="input"
              value={selectedProjectId ?? ""}
              onChange={(event) => setSelectedProjectId(event.target.value)}
              disabled={projectsLoading || chat.busy}
              aria-label="Select project for this conversation"
            >
              <option value="">General Q&amp;A (no project)</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            {showProminentPrompt ? (
              <span className="chat-project-select-hint muted">
                {selectedProject
                  ? `Files and workflows will use ${selectedProject.name}.`
                  : "Select a project before attaching engineering files."}
              </span>
            ) : null}
          </label>
          <div className="chat-header-status">
            <span className="chat-connection-status">{user ? "Signed in" : "Offline"}</span>
            <button
              type="button"
              className="button secondary chat-context-toggle"
              onClick={() => setContextOpen((value) => !value)}
              aria-expanded={contextOpen}
              aria-label={contextOpen ? "Hide project context" : "Show project context"}
            >
              {contextOpen ? "Hide context" : "Context"}
            </button>
          </div>
        </header>

        {chat.error ? (
          <div
            className="alert error chat-error-banner"
            role="alert"
            aria-live="assertive"
          >
            <span>{chat.error}</span>
            <div className="chat-error-actions">
              {chat.retryRequest ? (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => void chat.handleRetry()}
                  disabled={chat.busy}
                >
                  Retry
                </button>
              ) : null}
              <button
                type="button"
                className="chat-error-dismiss"
                onClick={chat.handleDismissError}
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : null}

        {showProminentPrompt ? (
          <div className="chat-hero">
            <div className="chat-hero-intro">
              <p className="chat-hero-eyebrow">Structural Engineering AI</p>
              <h1 className="chat-hero-title">StructuralAIAgent</h1>
              <p className="chat-hero-subtitle">
                Tell StructuralAIAgent what you want to accomplish.
              </p>
              <p className="chat-hero-lead">
                Describe a structural engineering task, attach models or documents when needed,
                and continue the conversation from one workspace.
              </p>
            </div>
            <div className="chat-hero-composer">
              <ChatComposer
                variant="prominent"
                hintId="chat-hero-composer-hint"
                {...composerProps}
              />
              <PromptExamples onSelect={handleExampleSelect} disabled={chat.busy} />
            </div>
          </div>
        ) : (
          <div className="chat-conversation-panel">
            <div className="chat-main-body">
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
            <ChatComposer variant="default" {...composerProps} />
          </div>
        )}
      </section>

      <ChatContextPanel
        projectId={selectedProjectId || null}
        projectName={selectedProject?.name ?? null}
        activeCapability={latestEngineering?.selectedCapability ?? null}
        executionStatus={latestEngineering?.executionStatus ?? chat.statusLabel}
        agentRun={latestEngineering?.agentRun ?? null}
        selectedFile={selectedFile}
        open={contextOpen}
        onClose={() => setContextOpen(false)}
        onUseFileInChat={(file) => {
          chat.attachExistingProjectFile(file);
        }}
        onDownloadFile={(file) => {
          if (!selectedProjectId) {
            return;
          }
          void downloadProjectFile(selectedProjectId, file.id, file.filename).catch((err) => {
            chat.setError(err instanceof Error ? err.message : "Download failed.");
          });
        }}
      />
    </div>
  );
}
