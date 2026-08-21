"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import {
  AVAILABLE_TOOL_OPTIONS,
  getAssistantTypeLabel,
  getLifecycleLabel,
  getLifecycleStage,
  getPublicationStatusLabel,
  getVersionStatusLabel,
} from "@/lib/agent-builder";
import {
  createBuilderAgent,
  getBuilderDetail,
  listAgentCapabilities,
  listBuilderPublications,
  listBuilderTests,
  listProjectAgents,
  publishBuilderVersion,
  rollbackBuilderAgent,
  testBuilderVersion,
  updateBuilderDraft,
  validateBuilderVersion,
  type AgentBuilderDetail,
  type AgentBuilderPublicationSummary,
  type EngineeringAgentType,
  type ProjectListResponse,
} from "@/lib/api";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const ASSISTANT_TYPES: EngineeringAgentType[] = [
  "VALIDATION_AGENT",
  "ANALYSIS_AGENT",
  "CONCRETE_DESIGN_AGENT",
  "STEEL_DESIGN_AGENT",
  "SEISMIC_AGENT",
  "CAD_AGENT",
  "REPORTING_AGENT",
  "DOCUMENT_INTERPRETATION_AGENT",
  "LOAD_ASSESSMENT_AGENT",
  "STRUCTURAL_MODELING_AGENT",
];

export default function AgentBuilderClient() {
  const [projects, setProjects] = useState<ProjectListResponse["projects"]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [agents, setAgents] = useState<AgentBuilderDetail["agent"][]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [detail, setDetail] = useState<AgentBuilderDetail | null>(null);
  const [capabilities, setCapabilities] = useState<Array<{ key: string; name: string }>>([]);
  const [tests, setTests] = useState<Array<{ id: string; created_at: string; validation_status: string | null }>>(
    [],
  );
  const [publications, setPublications] = useState<AgentBuilderPublicationSummary[]>([]);
  const [name, setName] = useState("");
  const [assistantType, setAssistantType] = useState<EngineeringAgentType>("VALIDATION_AGENT");
  const [instructions, setInstructions] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>(["project.validate"]);
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([]);
  const [testRequest, setTestRequest] = useState("Validate the current project configuration.");
  const [rollbackVersion, setRollbackVersion] = useState("1");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refreshAgentDetail = useCallback(async (agentId: string, version: number) => {
    const [validation, testResponse, publicationResponse] = await Promise.all([
      validateBuilderVersion(agentId, version),
      listBuilderTests(agentId, version),
      listBuilderPublications(agentId),
    ]);
    setTests(testResponse.tests);
    setPublications(publicationResponse.publications);
    setDetail((current) =>
      current
        ? {
            ...current,
            validation,
          }
        : current,
    );
  }, []);

  useEffect(() => {
    async function loadInitial() {
      setLoading(true);
      setError(null);
      try {
        const projectResponse = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/v1/projects`,
        ).then((response) => response.json() as Promise<ProjectListResponse>);
        const capabilityResponse = await listAgentCapabilities();
        setProjects(projectResponse.projects);
        setCapabilities(capabilityResponse.map((item) => ({ key: item.key, name: item.name })));
        const projectId = projectResponse.projects[0]?.id ?? "";
        setSelectedProjectId(projectId);
        if (projectId) {
          const agentResponse = await listProjectAgents(projectId);
          setAgents(agentResponse.agents);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load assistant builder");
      } finally {
        setLoading(false);
      }
    }
    void loadInitial();
  }, []);

  async function handleProjectChange(projectId: string) {
    setSelectedProjectId(projectId);
    setSelectedAgentId("");
    setDetail(null);
    try {
      const agentResponse = await listProjectAgents(projectId);
      setAgents(agentResponse.agents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project assistants");
    }
  }

  async function handleCreateAgent(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !name.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const created = await createBuilderAgent({
        key: `${name.trim().toLowerCase().replace(/\s+/g, "-")}-${Date.now()}`,
        name: name.trim(),
        agent_type: assistantType,
        project_id: selectedProjectId,
        instructions: instructions.trim(),
        capability_keys: selectedCapabilities,
      });
      setDetail(created);
      setSelectedAgentId(created.agent.id);
      const agentResponse = await listProjectAgents(selectedProjectId);
      setAgents(agentResponse.agents);
      setMessage("Draft assistant created.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create assistant");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveDraft() {
    if (!detail) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await updateBuilderDraft(detail.agent.id, detail.version.version, {
        instructions: instructions.trim(),
        configuration_metadata: {
          allowed_tools: selectedTools,
          model_configuration: detail.version.configuration_metadata.model_configuration ?? {},
        },
        capability_keys: selectedCapabilities,
      });
      setDetail(updated);
      setMessage("Draft saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save draft");
    } finally {
      setBusy(false);
    }
  }

  async function handleValidate() {
    if (!detail) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const validation = await validateBuilderVersion(detail.agent.id, detail.version.version);
      setDetail({ ...detail, validation });
      setMessage(validation.valid ? "Configuration is ready for testing." : "Configuration needs attention.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    if (!detail || !selectedProjectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await testBuilderVersion(
        detail.agent.id,
        detail.version.version,
        selectedProjectId,
        testRequest.trim(),
      );
      await refreshAgentDetail(detail.agent.id, detail.version.version);
      setMessage("Test completed without activating this version.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    if (!detail || !selectedProjectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const publication = await publishBuilderVersion(
        detail.agent.id,
        detail.version.version,
        selectedProjectId,
      );
      await refreshAgentDetail(detail.agent.id, detail.version.version);
      setMessage(
        publication.approval_request_id
          ? "Publish request sent for engineer review."
          : "Assistant version published.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Publish request failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleRollback() {
    if (!detail || !selectedProjectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await rollbackBuilderAgent(detail.agent.id, selectedProjectId, Number(rollbackVersion));
      await refreshAgentDetail(detail.agent.id, detail.version.version);
      setMessage("Rollback request sent for engineer review.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback request failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSelectAgent(agentId: string) {
    setSelectedAgentId(agentId);
    const agent = agents.find((item) => item.id === agentId);
    if (!agent) {
      return;
    }
    const versionNumber = agent.current_version ?? 1;
    try {
      const loaded = await getBuilderDetail(agentId, versionNumber);
      setDetail(loaded);
      setInstructions(loaded.version.instructions ?? "");
      setSelectedCapabilities(loaded.version.capabilities.map((item) => item.key));
      const tools = loaded.version.configuration_metadata.allowed_tools;
      setSelectedTools(Array.isArray(tools) ? tools.map(String) : ["project.validate"]);
      await refreshAgentDetail(agentId, versionNumber);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load assistant detail");
    }
  }

  const lifecycle = useMemo(() => {
    if (!detail) {
      return "draft" as const;
    }
    const pendingPublication = publications.find((item) => item.status === "PENDING_APPROVAL");
    return getLifecycleStage(
      detail.version.status,
      tests.length > 0,
      pendingPublication?.status ?? null,
    );
  }, [detail, publications, tests.length]);

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Assistant Builder</p>
        <h2>Configure engineering assistants</h2>
        <p className="subtitle">
          Create, test, review, and publish project assistants without touching internal runtime
          details.
        </p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={(projectId) => void handleProjectChange(projectId)}
        loading={loading}
      />

      {error ? <div className="alert error">{error}</div> : null}
      {message ? <div className="alert success">{message}</div> : null}

      <section className="card">
        <h3>Create a new assistant</h3>
        <form className="builder-form" onSubmit={handleCreateAgent}>
          <label>
            Assistant name
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Example: Project validation assistant"
              disabled={busy}
            />
          </label>
          <label>
            Purpose
            <select
              className="input"
              value={assistantType}
              onChange={(event) => setAssistantType(event.target.value as EngineeringAgentType)}
              disabled={busy}
            >
              {ASSISTANT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {getAssistantTypeLabel(type)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Instructions
            <textarea
              className="input request-input"
              rows={4}
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
              placeholder="Describe what this assistant should do for engineers."
              disabled={busy}
            />
          </label>
          <fieldset>
            <legend>Capabilities</legend>
            <div className="checkbox-grid">
              {capabilities.map((capability) => (
                <label key={capability.key} className="checkbox-line">
                  <input
                    type="checkbox"
                    checked={selectedCapabilities.includes(capability.key)}
                    onChange={(event) => {
                      setSelectedCapabilities((current) =>
                        event.target.checked
                          ? [...current, capability.key]
                          : current.filter((item) => item !== capability.key),
                      );
                    }}
                  />
                  {capability.name}
                </label>
              ))}
            </div>
          </fieldset>
          <button className="button" type="submit" disabled={busy || !selectedProjectId}>
            Create draft
          </button>
        </form>
      </section>

      {agents.length > 0 ? (
        <section className="card">
          <h3>Project assistants</h3>
          <ul className="workspace-list">
            {agents.map((agent) => (
              <li key={agent.id} className="workspace-list-item compact">
                <button
                  className="link-button"
                  type="button"
                  onClick={() => void handleSelectAgent(agent.id)}
                >
                  {agent.name}
                </button>
                <span className="muted">
                  {getAssistantTypeLabel(agent.agent_type)} · Version {agent.current_version ?? "draft"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {detail ? (
        <section className="card">
          <div className="execution-card-header">
            <div>
              <h3>{detail.agent.name}</h3>
              <p className="muted">
                {getAssistantTypeLabel(detail.agent.agent_type)} ·{" "}
                {getVersionStatusLabel(detail.version.status)}
              </p>
            </div>
            <span className={`progress-badge progress-${lifecycle}`}>{getLifecycleLabel(lifecycle)}</span>
          </div>

          <div className="builder-grid">
            <label>
              Instructions
              <textarea
                className="input request-input"
                rows={5}
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
              />
            </label>
            <fieldset>
              <legend>Available tools</legend>
              <div className="checkbox-grid">
                {AVAILABLE_TOOL_OPTIONS.map((tool) => (
                  <label key={tool.id} className="checkbox-line">
                    <input
                      type="checkbox"
                      checked={selectedTools.includes(tool.id)}
                      onChange={(event) => {
                        setSelectedTools((current) =>
                          event.target.checked
                            ? [...current, tool.id]
                            : current.filter((item) => item !== tool.id),
                        );
                      }}
                    />
                    {tool.label}
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

          {detail.validation.issues.length > 0 ? (
            <ul className="plan-list">
              {detail.validation.issues.map((issue) => (
                <li key={issue.code}>{issue.message}</li>
              ))}
            </ul>
          ) : null}

          <label>
            Test request
            <textarea
              className="input request-input"
              rows={3}
              value={testRequest}
              onChange={(event) => setTestRequest(event.target.value)}
            />
          </label>

          <div className="form-actions">
            <button className="button secondary" type="button" disabled={busy} onClick={() => void handleSaveDraft()}>
              Save draft
            </button>
            <button className="button secondary" type="button" disabled={busy} onClick={() => void handleValidate()}>
              Validate
            </button>
            <button className="button secondary" type="button" disabled={busy} onClick={() => void handleTest()}>
              Test
            </button>
            <button className="button" type="button" disabled={busy} onClick={() => void handlePublish()}>
              Request publish
            </button>
          </div>

          <div className="builder-grid">
            <label>
              Rollback to version
              <input
                className="input"
                value={rollbackVersion}
                onChange={(event) => setRollbackVersion(event.target.value)}
              />
            </label>
            <div className="form-actions align-end">
              <button className="button secondary" type="button" disabled={busy} onClick={() => void handleRollback()}>
                Request rollback
              </button>
            </div>
          </div>

          {tests.length > 0 ? (
            <>
              <p className="result-label">Recent tests</p>
              <ul className="plan-list">
                {tests.map((test) => (
                  <li key={test.id}>
                    {new Date(test.created_at).toLocaleString()} ·{" "}
                    {test.validation_status ?? "Recorded"}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {publications.length > 0 ? (
            <>
              <p className="result-label">Publication history</p>
              <ul className="plan-list">
                {publications.map((publication) => (
                  <li key={publication.id}>
                    Version {publication.agent_version} · {publication.action} ·{" "}
                    {getPublicationStatusLabel(publication.status)}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
