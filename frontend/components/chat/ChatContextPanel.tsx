"use client";

import {
  getProjectContext,
  getProjectMemoryContext,
  listProjectFiles,
  type MemorySummary,
  type ProjectContextResponse,
  type ProjectFileSummary,
} from "@/lib/api";
import { projectFileAvailabilityLabel, projectFileTypeLabel } from "@/lib/project-files";
import { getFileStatusLabel, getMemoryTypeLabel } from "@/lib/workspace";
import type { AgentRun } from "@/lib/chat-types";
import Link from "next/link";
import { useEffect, useState } from "react";

type ChatContextPanelProps = {
  projectId: string | null;
  projectName: string | null;
  activeCapability: string | null;
  executionStatus: string | null;
  agentRun?: AgentRun | null;
  selectedFile?: ProjectFileSummary | null;
  open: boolean;
  onClose: () => void;
  onUseFileInChat?: (file: ProjectFileSummary) => void;
  onDownloadFile?: (file: ProjectFileSummary) => void;
};

export function ChatContextPanel({
  projectId,
  projectName,
  activeCapability,
  executionStatus,
  agentRun,
  selectedFile = null,
  open,
  onClose,
  onUseFileInChat,
  onDownloadFile,
}: ChatContextPanelProps) {
  const [context, setContext] = useState<ProjectContextResponse | null>(null);
  const [files, setFiles] = useState<ProjectFileSummary[]>([]);
  const [memories, setMemories] = useState<MemorySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!projectId) {
      setContext(null);
      setFiles([]);
      setMemories([]);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      getProjectContext(projectId),
      listProjectFiles(projectId),
      getProjectMemoryContext(projectId),
    ])
      .then(([projectContext, fileResponse, memoryResponse]) => {
        if (cancelled) {
          return;
        }
        setContext(projectContext);
        setFiles(fileResponse.files);
        setMemories(memoryResponse.memories.slice(0, 8));
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load project context");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, reloadKey]);

  return (
    <aside className="chat-context-panel" data-open={open} aria-label="Project context">
      <header className="chat-context-header">
        <div>
          <p className="eyebrow">Project context</p>
          <h2>{projectName ?? "No project selected"}</h2>
        </div>
        <button
          type="button"
          className="chat-context-close"
          onClick={onClose}
          aria-label="Close project context"
        >
          ×
        </button>
      </header>

      {!projectId ? (
        <p className="muted">Select a project to see files, memory, and engineering status.</p>
      ) : null}

      {loading ? <p className="muted">Loading project context…</p> : null}

      {error ? (
        <div className="alert error">
          <p>{error}</p>
          <button type="button" className="button secondary" onClick={() => setReloadKey((value) => value + 1)}>
            Retry
          </button>
        </div>
      ) : null}

      {projectId && !loading && !error ? (
        <>
          <section className="chat-context-section">
            <p className="chat-sidebar-label">Task</p>
            <p>{executionStatus ? executionStatus.replace(/_/g, " ") : "Idle"}</p>
            <p className="muted">
              Active agent: {activeCapability ?? "None yet — send a request to route an agent"}
            </p>
            {agentRun?.lifecycle ? (
              <p className="muted">Lifecycle: {agentRun.lifecycle.replace(/_/g, " ")}</p>
            ) : null}
            {agentRun?.validationStatus ? (
              <p className="muted">Validation: {agentRun.validationStatus.replace(/_/g, " ")}</p>
            ) : null}
            {agentRun?.requiresApproval ? (
              <p className="chat-progress-badge warning">Approval required</p>
            ) : null}
          </section>

          <section className="chat-context-section">
            <p className="chat-sidebar-label">Code / units</p>
            {context?.code_configuration ? (
              <ul className="chat-context-list">
                <li>Jurisdiction: {context.code_configuration.jurisdiction}</li>
                <li>Building code: {context.code_configuration.governing_building_code}</li>
                <li>Concrete: {context.code_configuration.concrete_standard}</li>
                <li>Steel: {context.code_configuration.steel_standard}</li>
              </ul>
            ) : (
              <p className="muted">Project code profile is not configured yet.</p>
            )}
          </section>

          {selectedFile ? (
            <section className="chat-context-section" aria-label="Selected project file">
              <p className="chat-sidebar-label">Selected file</p>
              <ul className="chat-context-list">
                <li>File: {selectedFile.filename}</li>
                <li>Type: {projectFileTypeLabel(selectedFile.filename, selectedFile.file_type)}</li>
                <li>Status: {projectFileAvailabilityLabel(selectedFile)}</li>
                <li>Project: {projectName ?? "Current project"}</li>
              </ul>
              <div className="tool-execution-toggle">
                {onUseFileInChat ? (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => onUseFileInChat(selectedFile)}
                  >
                    Use in chat
                  </button>
                ) : null}
                {onDownloadFile ? (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => onDownloadFile(selectedFile)}
                  >
                    Download
                  </button>
                ) : null}
              </div>
            </section>
          ) : null}

          <section className="chat-context-section">
            <p className="chat-sidebar-label">Files</p>
            {files.length === 0 ? (
              <p className="muted">Upload an engineering document to begin.</p>
            ) : (
              <ul className="chat-context-list">
                {files.slice(0, 8).map((file) => (
                  <li key={file.id}>
                    {file.filename}
                    <span className="muted"> · {getFileStatusLabel(file.extraction_status)}</span>
                  </li>
                ))}
              </ul>
            )}
            <Link href="/workspace/files" className="chat-sidebar-link">
              Open files
            </Link>
          </section>

          <section className="chat-context-section">
            <p className="chat-sidebar-label">Project memory</p>
            {memories.length === 0 ? (
              <p className="muted">No project memory recorded yet.</p>
            ) : (
              <ul className="chat-context-list">
                {memories.map((memory) => (
                  <li key={memory.id}>
                    <strong>{getMemoryTypeLabel(memory.memory_type)}</strong>
                    <p className="muted">{truncate(memory.content, 140)}</p>
                  </li>
                ))}
              </ul>
            )}
            <Link href="/workspace/memory" className="chat-sidebar-link">
              Open memory
            </Link>
          </section>
        </>
      ) : null}
    </aside>
  );
}

function truncate(value: string, max: number): string {
  if (value.length <= max) {
    return value;
  }
  return `${value.slice(0, max - 1)}…`;
}
