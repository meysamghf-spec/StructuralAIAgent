"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { getTraceabilityGraph, type TraceabilityLinkSummary } from "@/lib/api";
import {
  formatWorkspaceDate,
  getTraceObjectLabel,
  getTraceRelationshipLabel,
} from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

export default function TraceabilityWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [links, setLinks] = useState<TraceabilityLinkSummary[]>([]);

  const refresh = useCallback(async (projectId: string) => {
    if (!projectId) {
      setLinks([]);
      return;
    }
    const response = await getTraceabilityGraph(projectId);
    setLinks(Array.isArray(response?.links) ? response.links : []);
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      setError(null);
      refresh(selectedProjectId).catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load traceability"),
      );
    }
  }, [selectedProjectId, refresh, setError]);

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Lineage</p>
        <h2 className="page-dup-title">Traceability</h2>
        <p className="subtitle">See how files, decisions, and results connect.</p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <h3>Engineering chain</h3>
        {links.length === 0 ? (
          <p className="muted">No links yet. Upload files or run an analysis to build lineage.</p>
        ) : null}
        <ul className="trace-list">
          {links.map((link) => (
            <li key={link.id} className="trace-item">
              <div className="trace-flow">
                <span>{getTraceObjectLabel(link.source_type)}</span>
                <span className="trace-arrow">→</span>
                <span>{getTraceRelationshipLabel(link.relationship_type)}</span>
                <span className="trace-arrow">→</span>
                <span>{getTraceObjectLabel(link.target_type)}</span>
              </div>
              <p className="muted">{formatWorkspaceDate(link.created_at)}</p>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
