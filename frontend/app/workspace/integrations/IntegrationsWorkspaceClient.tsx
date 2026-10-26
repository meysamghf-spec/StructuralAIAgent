"use client";

import { listAutocadJobs } from "@/lib/autocad";
import Link from "next/link";
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
  const [cadCount, setCadCount] = useState<number | null>(null);

  useEffect(() => {
    listAutocadJobs(selectedProjectId).then((j) => setCadCount(j.length)).catch(() => setCadCount(null));
  }, [selectedProjectId]);

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
            {capability.software === "SAP2000" ? (
              <p className="muted" data-testid="sap2000-s2k-note">
                Built in: SAP2000 model export (.s2k, no local install needed). In the chat ask «خروجی SAP2000» /
                &quot;export SAP2000&quot; after a 3D frame analysis, or download model.s2k from the CAD or Model page.
              </p>
            ) : null}
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
        <article className="card" id="autocad" data-testid="autocad-integration-card">
          <h3>AutoCAD (DXF R2018)</h3>
          <p className={`status-pill ${getAvailabilityClass("AVAILABLE")}`}>{getAvailabilityLabel("AVAILABLE")}</p>
          <p className="muted">
            Built in, no local install needed. In the chat, attach a PDF or photo of a plan and ask to convert it to DXF, or
            describe a floor plan to draw it. Output: layered DXF (NCS layers, title block) that opens in AutoCAD.
          </p>
          <p className="muted">داخلی؛ در چت فایل PDF یا عکس نقشه را پیوست کنید یا نقشه را توصیف کنید.</p>
          <p className="muted">
            Exports: .dxf{cadCount !== null ? ` · ${cadCount} drawing${cadCount === 1 ? "" : "s"}${selectedProjectId ? " in this project" : ""}` : ""}
          </p>
          <div className="form-row">
            <Link className="button secondary" href="/">
              Use in chat
            </Link>
            <Link className="button" href="/workspace/cad">
              Open drawings
            </Link>
          </div>
        </article>
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
