"use client";

import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatContextPanel } from "@/components/chat/ChatContextPanel";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatCardProjectContext } from "@/lib/chat-card-project";
import { ProjectSwitcher } from "@/components/project/ProjectSwitcher";
import { ProjectMemoryBadge } from "@/components/chat/ProjectMemoryBadge";
import { AssistantContextStrip } from "@/components/chat/AssistantContextStrip";
import { ChatThread } from "@/components/chat/ChatThread";
import { SaiaLogo } from "@/components/brand/SaiaLogo";
import { useUiLang } from "@/hooks/useUiLang";
import { useAuth } from "@/hooks/useAuth";
import { useChat } from "@/hooks/useChat";
import { useProjectFiles } from "@/hooks/useProjectFiles";
import { useProjectScope } from "@/hooks/useProjectScope";
import { downloadProjectFile, uploadProjectFile, type ProjectFileSummary } from "@/lib/api";
import { clearStoredActiveConversations, shouldShowProminentPrompt } from "@/lib/chat";
import { mapBackendMessage } from "@/lib/chat-mappers";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

export default function ChatWorkspace() {
  const { t } = useUiLang();
  const { user, isAuthenticated, loading: authLoading, logout } = useAuth();
  const router = useRouter();
  const composerInputRef = useRef<HTMLTextAreaElement>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<ProjectFileSummary | null>(null);
  const [filesRefreshToken, setFilesRefreshToken] = useState(0);
  const [assistant, setAssistant] = useState<string | null>(null);
  const [urlProject, setUrlProject] = useState<string | null>(null);
  const [urlPrompt, setUrlPrompt] = useState<string | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setAssistant(params.get("assistant"));
    setUrlProject(params.get("project"));
    setUrlPrompt(params.get("prompt"));
  }, []);
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    selectedProject,
    loading: projectsLoading,
    refreshProjects,
  } = useProjectScope(urlProject);

  const chat = useChat({
    isAuthenticated,
    authLoading,
    selectedProjectId,
    setSelectedProjectId,
    assistant,
    projectsReady: !projectsLoading,
    onChatAction: (action) => {
      if (action.switchAssistant) setAssistant(action.switchAssistant);
      if (action.projectSwitch) void refreshProjects().catch(() => undefined);
    },
  });
  const setChatContent = chat.setContent;
  useEffect(() => {
    // ?prompt=… (e.g. from the Optimization checklist) pre-fills the composer; the user still presses Send.
    if (urlPrompt) setChatContent(urlPrompt.slice(0, 2000));
  }, [urlPrompt, setChatContent]);
  const projectFiles = useProjectFiles(selectedProjectId || null, filesRefreshToken);

  useEffect(() => {
    setSelectedFile(null);
  }, [selectedProjectId]);

  const activeConversation =
    chat.conversations.find((item) => item.id === chat.activeConversationId) ??
    chat.generalConversations.find((item) => item.id === chat.activeConversationId);

  // Open conversation is an older chat that never had a project (listed under "General").
  const legacyChatOpen =
    Boolean(selectedProjectId) &&
    chat.generalConversations.some((item) => item.id === chat.activeConversationId);

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
      latestEngineering?.frame3dResults ||
      latestEngineering?.requiresApproval,
  );

  useEffect(() => {
    // On phones/tablets the context panel is an overlay; don't auto-open it over the chat.
    if (hasStructuredContext && (typeof window === "undefined" || window.innerWidth > 1200)) {
      setContextOpen(true);
    }
  }, [
    hasStructuredContext,
    latestEngineering?.approvalRequestId,
    latestEngineering?.agentRun?.lifecycle,
    latestEngineering?.demoResults?.kind,
    latestEngineering?.aciBeamResults?.kind,
    latestEngineering?.frame3dResults?.kind,
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
    onStop: chat.handleStop,
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
    clearStoredActiveConversations();
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
          <p className="eyebrow">{t("Chat with your structural AI")}</p>
          <h2>{t("Chat-first, AI-driven structural engineering")}</h2>
          <p className="subtitle">{t("Analysis, design, validation, approval and memory — all in one conversation.")}</p>
        </header>
        <div className="card">
          <p>
            <Link href="/login">Sign in</Link> or <Link href="/register">create an account</Link>{" "}
            to start chatting.
          </p>
        </div>
      </section>
    );
  }

  return (
    <div className="chat-shell" data-context-open={contextOpen ? "true" : "false"}>
      <ChatSidebar
        conversations={chat.conversations}
        generalConversations={chat.generalConversations}
        projectScope={{ projects, selectedProjectId, selectedProject, setSelectedProjectId }}
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
        onRenameConversation={(id, title) => void chat.handleRenameConversation(id, title)}
        selectedProjectId={selectedProjectId || ""}
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
                <SaiaLogo size="sm" tagline={false} className="chat-header-logo" />
                <h2>{activeConversation?.title ?? t("New chat")}</h2>
                {selectedProject ? (
                  <span className="chat-project-badge">{t("Project")}: {selectedProject.name}</span>
                ) : (
                  <span className="chat-project-badge muted">
                    No project selected — required for file attachments
                  </span>
                )}
              </div>
            ) : (
              <SaiaLogo size="md" className="chat-header-logo" />
            )}
          </div>
          <div className="chat-project-select">
            <ProjectSwitcher
              variant="bar"
              disabled={projectsLoading || chat.busy}
              scope={{ projects, selectedProjectId, selectedProject, setSelectedProjectId }}
            />
            <ProjectMemoryBadge projectId={selectedProjectId ?? null} refreshKey={chat.busy} />
            {showProminentPrompt ? (
              <span className="chat-project-select-hint muted" dir="auto">
                {selectedProject
                  ? t("This chat and its model, results and reports belong to this project.")
                  : t("Create a project first — chats, files and results are kept per project.")}
              </span>
            ) : null}
          </div>
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
            {assistant ? (
              <AssistantContextStrip
                assistant={assistant}
                onPick={handleExampleSelect}
                onClear={() => setAssistant(null)}
                disabled={chat.busy}
              />
            ) : null}
            <div className="chat-hero-intro">
              <p className="chat-hero-eyebrow">{t("Chat with your structural AI")}</p>
              <h1 className="chat-hero-title"><SaiaLogo size="lg" /></h1>
              <p className="chat-hero-subtitle">
                Tell SAIA what you want to accomplish.
              </p>
              <p className="chat-hero-lead">
                {t("Analysis, design, validation, approval and memory — all in one conversation.")}
              </p>
            </div>
            <div className="chat-hero-composer">
              <ChatComposer
                variant="prominent"
                hintId="chat-hero-composer-hint"
                {...composerProps}
              />
            </div>
          </div>
        ) : (
          <div className="chat-conversation-panel">
            {assistant ? (
              <AssistantContextStrip
                assistant={assistant}
                onPick={handleExampleSelect}
                onClear={() => setAssistant(null)}
                disabled={chat.busy}
              />
            ) : null}
            <div className="chat-main-body">
              <ChatCardProjectContext.Provider value={legacyChatOpen ? null : undefined}>
              <ChatThread
                messages={chat.messages}
                busy={chat.busy}
                loadingMessages={chat.loadingMessages}
                executionPhase={chat.executionPhase}
                statusLabel={chat.statusLabel}
                projectId={selectedProjectId || null}
                projectName={selectedProject?.name ?? null}
                onApprovalResolved={() => void chat.handleApprovalResolved()}
                onRegenerate={() => void chat.handleRegenerate()}
              />
              </ChatCardProjectContext.Provider>
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
