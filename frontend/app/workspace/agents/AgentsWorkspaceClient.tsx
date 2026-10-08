"use client";

import { AgentOverviewGrid } from "@/components/agents/AgentOverviewGrid";
import { ExecutionHistoryList } from "@/components/agents/ExecutionHistoryList";
import { buildAssistantProfiles } from "@/lib/agent-workspace";
import {
  apiFetch,
  createAgentExecution,
  getCurrentPemIdentity,
  listAgentExecutions,
  listAgents,
  listProjectFiles,
  planAgentExecution,
  uploadProjectFile,
  type AgentExecutionSummary,
  type CurrentPemIdentity,
  type EngineeringAgentType,
  type ProjectFileSummary,
  type ProjectListResponse,
  type PromptGenerationResult,
} from "@/lib/api";
import { filesForProject, productionRunAllowed } from "@/lib/engineering-workspace";
import { listCadDrawings, type CadDrawing } from "@/lib/cad";
import { RequestPlanPanel } from "@/components/agents/RequestPlanPanel";
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
  const [planning, setPlanning] = useState(false);
  const [requestPlan, setRequestPlan] = useState<PromptGenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [assistants, setAssistants] = useState(buildAssistantProfiles([]));
  const [selectedAgentType, setSelectedAgentType] = useState<EngineeringAgentType | "">("");
  const [pem, setPem] = useState<CurrentPemIdentity | null>(null);
  const [files, setFiles] = useState<ProjectFileSummary[]>([]);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [drawings, setDrawings] = useState<CadDrawing[]>([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);

  const refreshProjectContext = useCallback(async (projectId: string) => {
    if (!projectId) {
      setExecutions([]);
      setFiles([]);
      setDrawings([]);
      setPem(null);
      setSelectedFileIds([]);
      setSelectedExecutionId(null);
      return;
    }
    const [executionResponse, fileResponse, pemIdentity, drawingResponse] = await Promise.all([
      listAgentExecutions(projectId),
      listProjectFiles(projectId),
      getCurrentPemIdentity(projectId),
      listCadDrawings(projectId).catch(() => [] as CadDrawing[]),
    ]);
    setExecutions(executionResponse.executions);
    setFiles(filesForProject(fileResponse.files, projectId));
    setPem(pemIdentity);
    setDrawings(drawingResponse);
    setSelectedFileIds([]);
    setSelectedExecutionId(executionResponse.executions[0]?.id ?? null);
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
          await refreshProjectContext(projectId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load assistant workspace");
      } finally {
        setLoading(false);
      }
    }

    void loadInitial();
  }, [initialProjectId, refreshProjectContext]);

  async function handleProjectChange(projectId: string) {
    setSelectedProjectId(projectId);
    setError(null);
    try {
      await refreshProjectContext(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load activity history");
    }
  }

  async function handlePreviewPlan() {
    if (!selectedProjectId || !requestText.trim()) {
      return;
    }
    setPlanning(true);
    setError(null);
    try {
      const plan = await planAgentExecution(selectedProjectId, requestText.trim());
      setRequestPlan(plan);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview request plan");
    } finally {
      setPlanning(false);
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
      const created = await createAgentExecution({
        project_id: selectedProjectId,
        user_request: requestText.trim(),
        agent_type: selectedAgentType || undefined,
        parameters: selectedFileIds.length > 0 ? { attachment_file_ids: selectedFileIds } : undefined,
      });
      setRequestText("");
      setRequestPlan(null);
      setSelectedFileIds([]);
      await refreshProjectContext(selectedProjectId);
      setSelectedExecutionId(created.id);
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
  const selectedAssistant = useMemo(
    () => assistants.find((assistant) => assistant.agentType === selectedAgentType) ?? null,
    [assistants, selectedAgentType],
  );
  const canRun = Boolean(selectedProjectId) && productionRunAllowed(selectedAssistant) && !submitting;

  async function handleUpload(selected: FileList | null) {
    if (!selectedProjectId || !selected?.length) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const uploadedIds: string[] = [];
      for (const file of Array.from(selected)) {
        const record = await uploadProjectFile(selectedProjectId, file);
        if (!record.project_id || record.project_id === selectedProjectId) {
          uploadedIds.push(record.id);
        }
      }
      const fileResponse = await listProjectFiles(selectedProjectId);
      setFiles(filesForProject(fileResponse.files, selectedProjectId));
      setSelectedFileIds((current) => [...new Set([...current, ...uploadedIds])]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Engineering Assistants</p>
        <h2>Agent Workspace</h2>
        <p className="subtitle">
          Choose a project, an assistant, and the current engineering model. Runs stay traceable to
          that project, the PEM snapshot, and any approved learning used as context.
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
        <p className="muted">
          {pem
            ? `Current model${pem.name ? ` ${pem.name}` : ""} · version ${pem.version} · snapshot ${pem.snapshotId}`
            : "No current engineering model is stored for this project."}
        </p>
      </section>

      <section className="card">
        <h3>Assistant</h3>
        <select
          className="input"
          value={selectedAgentType}
          onChange={(event) => setSelectedAgentType(event.target.value as EngineeringAgentType | "")}
          disabled={!selectedProjectId || submitting}
        >
          <option value="">Route from the request</option>
          {assistants.map((assistant) => (
            <option key={assistant.id} value={assistant.agentType ?? ""} disabled={!assistant.agentType}>
              {assistant.title} · {assistant.status}
            </option>
          ))}
        </select>
        {selectedAssistant && !productionRunAllowed(selectedAssistant) ? (
          <p className="muted">
            {selectedAssistant.title} is {selectedAssistant.status.toLowerCase()} and cannot start a new
            production run. Earlier runs remain in the history below.
          </p>
        ) : null}
      </section>

      <section className="card">
        <h3>Project files</h3>
        <p className="muted">Only files stored on this project can be attached to a run.</p>
        <input
          className="input"
          type="file"
          multiple
          accept="application/pdf,image/*,.txt,.csv,.xlsx,.xls,.docx"
          disabled={!selectedProjectId || submitting}
          onChange={(event) => void handleUpload(event.target.files)}
        />
        {files.length === 0 ? (
          <p className="muted">No project files yet.</p>
        ) : (
          <ul className="workspace-list">
            {files.map((file) => (
              <li key={file.id} className="workspace-list-item compact">
                <label>
                  <input
                    type="checkbox"
                    checked={selectedFileIds.includes(file.id)}
                    onChange={(event) => {
                      setSelectedFileIds((current) =>
                        event.target.checked
                          ? [...current, file.id]
                          : current.filter((id) => id !== file.id),
                      );
                    }}
                  />{" "}
                  {file.filename}
                </label>
              </li>
            ))}
          </ul>
        )}
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
            onChange={(event) => {
              setRequestText(event.target.value);
              setRequestPlan(null);
            }}
            rows={4}
            disabled={!selectedProjectId || submitting}
          />
          <div className="form-actions">
            <button
              className="button secondary"
              type="button"
              disabled={!selectedProjectId || planning || submitting}
              onClick={() => void handlePreviewPlan()}
            >
              {planning ? "Understanding…" : "Preview understanding"}
            </button>
            <button className="button" type="submit" disabled={!canRun || !requestText.trim()}>
              {submitting ? "Submitting…" : "Run"}
            </button>
          </div>
        </form>
        {requestPlan ? <RequestPlanPanel plan={requestPlan} /> : null}
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      <section>
        <header className="section-header">
          <h3>Available assistants</h3>
          <p className="muted">Specialist engineering assistants available in your workspace.</p>
        </header>
        {loading ? (
          <p className="muted">Loading assistants…</p>
        ) : (
          <AgentOverviewGrid
            assistants={assistants}
            selectedAgentType={selectedAgentType || null}
            onSelect={(agentType) => {
              if (agentType) {
                setSelectedAgentType(agentType);
              }
            }}
          />
        )}
      </section>

      <section>
        <header className="section-header">
          <h3>Drawings and schedules</h3>
          <p className="muted">Generated CAD records for this project. Empty means none have been stored.</p>
        </header>
        {drawings.length === 0 ? (
          <p className="muted">No generated drawings are stored for this project.</p>
        ) : (
          <ul className="workspace-list">
            {drawings.map((drawing) => (
              <li key={drawing.id} className="workspace-list-item compact">
                <span>
                  {drawing.drawing_type} · {drawing.output_format} · {drawing.status}
                </span>
                <p className="muted">{drawing.validation_status}</p>
              </li>
            ))}
          </ul>
        )}
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
            onRefresh={() => void refreshProjectContext(selectedProjectId)}
            selectedExecutionId={selectedExecutionId}
            onSelectExecution={setSelectedExecutionId}
          />
        )}
      </section>
    </section>
  );
}
