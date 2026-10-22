"use client";

import { AutocadPanel } from "@/components/autocad/AutocadPanel";
import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  connectSolver,
  disconnectSolver,
  exportModelToSolver,
  listIntegrationExecutions,
  listSolverCapabilities,
  type IntegrationExecution,
  type SoftwareCapability,
} from "@/lib/integrations";
import {
  getAvailabilityClass,
  getAvailabilityLabel,
  getConnectionHelpMessage,
  getSoftwareDisplayName,
} from "@/lib/integrations-workspace";
import { runAnalysis } from "@/lib/analysis";
import { formatWorkspaceDate } from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

export default function IntegrationsWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [capabilities, setCapabilities] = useState<SoftwareCapability[]>([]);
  const [executions, setExecutions] = useState<IntegrationExecution[]>([]);
  const [busySoftware, setBusySoftware] = useState<string | null>(null);
  const [analysisSoftware, setAnalysisSoftware] = useState("ETABS");
  const [analysisMessage, setAnalysisMessage] = useState<string | null>(null);

  const loadIntegrationContext = useCallback(async () => {
    const capabilityData = await listSolverCapabilities();
    setCapabilities(capabilityData);
    if (!selectedProjectId) {
      setExecutions([]);
      return;
    }
    const executionData = await listIntegrationExecutions(selectedProjectId);
    setExecutions(executionData);
  }, [selectedProjectId]);

  useEffect(() => {
    async function load() {
      try {
        await loadIntegrationContext();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load integration workspace");
      }
    }
    void load();
  }, [loadIntegrationContext, setError]);

  async function handleConnect(software: string) {
    if (!selectedProjectId) return;
    setBusySoftware(software);
    setError(null);
    try {
      await connectSolver(selectedProjectId, software);
      await loadIntegrationContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setBusySoftware(null);
    }
  }

  async function handleDisconnect(software: string) {
    if (!selectedProjectId) return;
    setBusySoftware(software);
    setError(null);
    try {
      await disconnectSolver(selectedProjectId, software);
      await loadIntegrationContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setBusySoftware(null);
    }
  }

  async function handleExport(software: string) {
    if (!selectedProjectId) return;
    setBusySoftware(software);
    setError(null);
    try {
      await exportModelToSolver(selectedProjectId, software);
      await loadIntegrationContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusySoftware(null);
    }
  }

  async function handleRunAnalysis() {
    if (!selectedProjectId) return;
    setBusySoftware(analysisSoftware);
    setError(null);
    setAnalysisMessage(null);
    try {
      const result = await runAnalysis(selectedProjectId, "STATIC", {
        solver: analysisSoftware,
      });
      setAnalysisMessage(result.message);
      await loadIntegrationContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis run failed");
    } finally {
      setBusySoftware(null);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Integrations</p>
        <h2>Integrations</h2>
        <p className="subtitle">Connect local ETABS, SAP2000, or SAFE to export and analyze.</p>
      </header>

      <AutocadPanel />

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      <section className="grid cards-3">
        {capabilities.map((capability) => (
          <article className="card" key={capability.software}>
            <h3>{getSoftwareDisplayName(capability.software, capability.expected_version)}</h3>
            <p className={`status-pill ${getAvailabilityClass(capability.availability)}`}>
              {getAvailabilityLabel(capability.availability)}
            </p>
            <p className="muted">
              {getConnectionHelpMessage(
                capability.software,
                capability.expected_version,
                capability.availability,
              )}
            </p>
            {capability.message &&
            !getConnectionHelpMessage(
              capability.software,
              capability.expected_version,
              capability.availability,
            ).includes(capability.message) ? (
              <p className="muted">{capability.message}</p>
            ) : null}
            <p className="muted">
              {getAvailabilityLabel(capability.availability, "fa")}
            </p>
            {selectedProjectId ? (
              <div className="form-row">
                <button
                  className="button secondary"
                  type="button"
                  disabled={busySoftware === capability.software}
                  onClick={() => void handleConnect(capability.software)}
                >
                  Connect
                </button>
                <button
                  className="button secondary"
                  type="button"
                  disabled={busySoftware === capability.software}
                  onClick={() => void handleDisconnect(capability.software)}
                >
                  Disconnect
                </button>
                <button
                  className="button"
                  type="button"
                  disabled={busySoftware === capability.software}
                  onClick={() => void handleExport(capability.software)}
                >
                  Export model
                </button>
              </div>
            ) : (
              <p className="muted">Select a project to use export and analysis workflows.</p>
            )}
          </article>
        ))}
      </section>

      {selectedProjectId ? (
        <section className="card">
          <h3>Run analysis with local solver</h3>
          <div className="form-row">
            <select
              className="input"
              value={analysisSoftware}
              onChange={(event) => setAnalysisSoftware(event.target.value)}
            >
              <option value="ETABS">ETABS 23</option>
              <option value="SAP2000">SAP2000 27</option>
              <option value="SAFE">SAFE 23</option>
            </select>
            <button
              className="button"
              type="button"
              disabled={busySoftware !== null}
              onClick={() => void handleRunAnalysis()}
            >
              {busySoftware ? "Running…" : "Run analysis"}
            </button>
          </div>
          {analysisMessage ? <p className="muted">{analysisMessage}</p> : null}
        </section>
      ) : null}

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <h3>Integration history</h3>
        {executions.length === 0 ? (
          <p className="muted">No executions yet. Detect local software above to begin.</p>
        ) : (
          <ul className="timeline-list">
            {executions.map((execution) => (
              <li key={execution.id}>
                <strong>
                  {execution.software} · {execution.operation}
                </strong>
                <span>{execution.message}</span>
                <span className="muted">
                  {getAvailabilityLabel(execution.status)} · {formatWorkspaceDate(execution.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
