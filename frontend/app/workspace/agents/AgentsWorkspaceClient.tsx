"use client";

import { AgentOverviewGrid } from "@/components/agents/AgentOverviewGrid";
import { ExecutionHistoryList } from "@/components/agents/ExecutionHistoryList";
import { buildAssistantProfiles } from "@/lib/agent-workspace";
import {
  apiFetch,
  createAgentExecution,
  listAgentExecutions,
  listAgents,
  type AgentExecutionSummary,
  type ProjectListResponse,
} from "@/lib/api";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function AgentsWorkspaceClient() {
  const searchParams = useSearchParams();
  const initialProjectId = searchParams.get("project");
  const reviewApprovalId = searchParams.get("review");

  const [projects, setProjects] = useState<ProjectListResponse["projects"]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [executions, setExecutions] = useState<AgentExecutionSummary[]>([]);
  const [requestText, setRequestText] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assistants, setAssistants] = useState(buildAssistantProfiles([]));

  const refreshExecutions = useCallback(async (projectId: string) => {
    if (!projectId) {
      setExecutions([]);
      return;
    }
    const response = await listAgentExecutions(projectId);
    setExecutions(response.executions);
  }, []);

  useEffect(() => {
    async function loadInitial() {
      setLoading(true);
      setError(null);
      try {
        const [projectResponse, agentResponse] = await Promise.all([
          apiFetch<ProjectListResponse>("/api/v1/projects"),
          listAgents(),
        ]);
        setProjects(projectResponse.projects);
        setAssistants(buildAssistantProfiles(agentResponse.agents));

        const projectId =
          initialProjectId &&
          projectResponse.projects.some((project) => project.id === initialProjectId)
            ? initialProjectId
            : projectResponse.projects[0]?.id ?? "";
        setSelectedProjectId(projectId);
        if (projectId) {
          await refreshExecutions(projectId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load assistant workspace");
      } finally {
        setLoading(false);
      }
    }

    void loadInitial();
  }, [initialProjectId, refreshExecutions]);

  async function handleProjectChange(projectId: string) {
    setSelectedProjectId(projectId);
    setError(null);
    try {
      await refreshExecutions(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load activity history");
    }
  }

  async function handleSubmitRequest(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !requestText.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createAgentExecution({
        project_id: selectedProjectId,
        user_request: requestText.trim(),
      });
      setRequestText("");
      await refreshExecutions(selectedProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit request");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Engineering Assistants</p>
        <h2>Agent Workspace</h2>
        <p className="subtitle">
          Ask for structural engineering help, track progress, and review results without managing
          internal runtime details.
        </p>
      </header>

      <section className="card">
        <h3>Active project</h3>
        <p className="muted">Assistant activity is scoped to the selected project.</p>
        <select
          className="input project-select"
          value={selectedProjectId}
          onChange={(event) => void handleProjectChange(event.target.value)}
          disabled={loading || projects.length === 0}
        >
          {projects.length === 0 ? <option value="">No projects available</option> : null}
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        {selectedProject ? <p className="muted">Working in {selectedProject.name}</p> : null}
      </section>

      <section className="card">
        <h3>What do you need help with?</h3>
        <p className="muted">
          Describe your engineering request in plain language. The platform will route it to the
          right assistant.
        </p>
        <form className="request-form" onSubmit={handleSubmitRequest}>
          <textarea
            className="input request-input"
            placeholder="Example: Review the lateral load assumptions for the steel moment frame."
            value={requestText}
            onChange={(event) => setRequestText(event.target.value)}
            rows={4}
            disabled={!selectedProjectId || submitting}
          />
          <button className="button" type="submit" disabled={!selectedProjectId || submitting}>
            {submitting ? "Submitting…" : "Send request"}
          </button>
        </form>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      <section>
        <header className="section-header">
          <h3>Available assistants</h3>
          <p className="muted">Specialist engineering assistants available in your workspace.</p>
        </header>
        {loading ? <p className="muted">Loading assistants…</p> : <AgentOverviewGrid assistants={assistants} />}
      </section>

      <section>
        <header className="section-header">
          <h3>Recent activity</h3>
          <p className="muted">Track what was requested, current progress, and finalized results.</p>
        </header>
        {loading ? (
          <p className="muted">Loading activity…</p>
        ) : (
          <ExecutionHistoryList
            executions={executions}
            projectId={selectedProjectId}
            reviewApprovalId={reviewApprovalId}
            onRefresh={() => void refreshExecutions(selectedProjectId)}
          />
        )}
      </section>
    </section>
  );
}
