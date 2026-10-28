"use client";
import { useUiLang } from "@/hooks/useUiLang";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { getProjectMemoryContext, type MemorySummary } from "@/lib/api";
import { formatWorkspaceDate, getMemoryTypeLabel, truncateText } from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

export default function MemoryWorkspaceClient() {
  const { t } = useUiLang();
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [memories, setMemories] = useState<MemorySummary[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [countsByType, setCountsByType] = useState<Record<string, number>>({});

  const refresh = useCallback(async (projectId: string) => {
    if (!projectId) {
      setMemories([]);
      return;
    }
    const response = await getProjectMemoryContext(projectId);
    setMemories(Array.isArray(response?.memories) ? response.memories : []);
    setTotalCount(response?.total_count ?? 0);
    setCountsByType(response?.counts_by_type ?? {});
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      setError(null);
      refresh(selectedProjectId).catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load project memory"),
      );
    }
  }, [selectedProjectId, refresh, setError]);

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Knowledge</p>
        <h2 className="page-dup-title">Memory</h2>
        <p className="subtitle">What the platform remembers about this project.</p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      {error ? <div className="alert error">{error}</div> : null}

      <div className="grid cards-3">
        <article className="card">
          <h3>Total entries</h3>
          <p className="metric">{totalCount}</p>
        </article>
        {Object.entries(countsByType).slice(0, 2).map(([type, count]) => (
          <article key={type} className="card">
            <h3>{getMemoryTypeLabel(type)}</h3>
            <p className="metric">{count}</p>
          </article>
        ))}
      </div>

      <section className="card">
        <h3>Recent memory</h3>
        {memories.length === 0 ? (
          <div className="empty-state">
            <p>{t("No project memory recorded yet.")}</p>
            <p>{t("Memory is filled automatically when you analyse a frame or discuss decisions in the project chat.")}</p>
          </div>
        ) : null}
        <ul className="workspace-list">
          {memories.map((memory) => (
            <li key={memory.id} className="workspace-list-item compact">
              <div>
                <span className="status-pill status-available">{getMemoryTypeLabel(memory.memory_type)}</span>
                <p className="result-text">{truncateText(memory.content, 280)}</p>
                <p className="muted">{formatWorkspaceDate(memory.created_at)}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
