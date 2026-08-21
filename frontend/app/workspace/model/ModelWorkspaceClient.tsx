"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  formatModelCounts,
  getAnalysisStatusLabel,
  getRevisionChangeLabel,
} from "@/lib/model-workspace";
import {
  getCurrentModel,
  getModelSummary,
  listPemVersions,
  listRevisions,
  validateModel,
  type ModelSummaryResponse,
  type ModelValidationResponse,
  type RevisionSummary,
  type StructuralModelResponse,
} from "@/lib/model";
import { formatWorkspaceDate, getValidationStatusLabel } from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "pass") return "status-pass";
  if (normalized === "error") return "status-error";
  if (normalized === "warning") return "status-warning";
  return "status-review";
}

export default function ModelWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [summary, setSummary] = useState<ModelSummaryResponse | null>(null);
  const [model, setModel] = useState<StructuralModelResponse | null>(null);
  const [validation, setValidation] = useState<ModelValidationResponse | null>(null);
  const [versions, setVersions] = useState<number[]>([]);
  const [revisions, setRevisions] = useState<RevisionSummary[]>([]);
  const [busy, setBusy] = useState(false);

  const loadModelData = useCallback(async () => {
    if (!selectedProjectId) {
      setSummary(null);
      setModel(null);
      setValidation(null);
      setVersions([]);
      setRevisions([]);
      return;
    }
    setError(null);
    const [summaryData, modelData, versionData, revisionData] = await Promise.all([
      getModelSummary(selectedProjectId),
      getCurrentModel(selectedProjectId),
      listPemVersions(selectedProjectId),
      listRevisions(selectedProjectId),
    ]);
    setSummary(summaryData);
    setModel(modelData);
    setValidation(null);
    setVersions(versionData.versions);
    setRevisions(revisionData.revisions);
  }, [selectedProjectId, setError]);

  useEffect(() => {
    async function load() {
      try {
        await loadModelData();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load engineering model");
      }
    }
    void load();
  }, [loadModelData, setError]);

  async function handleValidate() {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    try {
      const report = await validateModel(selectedProjectId);
      setValidation(report);
      setSummary(await getModelSummary(selectedProjectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  }

  const structural = model?.structural_model as Record<string, unknown> | undefined;
  const geometry = (structural?.geometry ?? {}) as Record<string, unknown[]>;
  const materials = (structural?.materials ?? {}) as Record<string, unknown[]>;
  const sections = (structural?.sections ?? {}) as Record<string, unknown[]>;
  const members = ((structural?.members as { members?: unknown[] })?.members ?? []) as unknown[];
  const supports = (structural?.supports ?? []) as unknown[];
  const loadCases = (structural?.load_cases ?? []) as unknown[];
  const loadCombinations = (structural?.load_combinations ?? []) as unknown[];

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Model</p>
        <h2>Engineering Model</h2>
        <p className="subtitle">
          Review geometry, materials, members, loads, validation status, and revision history for the
          project engineering model.
        </p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      {error ? <div className="alert error">{error}</div> : null}

      {summary && model ? (
        <>
          <div className="grid cards-3">
            <article className="card">
              <h3>Model status</h3>
              <p className="metric">Version {summary.pem_version}</p>
              <p className="muted">{summary.project_name}</p>
              <p className={`status-pill ${statusClass(summary.validation_status)}`}>
                {getValidationStatusLabel(summary.validation_status)}
              </p>
              <p className="muted">
                Analysis: {getAnalysisStatusLabel(summary.analysis_status)}
              </p>
            </article>

            <article className="card">
              <h3>Model inventory</h3>
              <ul className="feature-list">
                {formatModelCounts(summary).map((item) => (
                  <li key={item.label}>
                    {item.label}: <strong>{item.value}</strong>
                  </li>
                ))}
              </ul>
            </article>

            <article className="card">
              <h3>Validation</h3>
              <button
                className="button"
                type="button"
                disabled={!selectedProjectId || busy}
                onClick={() => void handleValidate()}
              >
                {busy ? "Validating…" : "Validate model"}
              </button>
              {validation ? (
                <div className="stack-sm">
                  <p className={`status-pill ${statusClass(validation.overall_status)}`}>
                    {getValidationStatusLabel(validation.overall_status)}
                  </p>
                  <p className="muted">{validation.summary}</p>
                  {validation.findings.length > 0 ? (
                    <ul className="feature-list">
                      {validation.findings.slice(0, 6).map((finding, index) => (
                        <li key={`${finding.code}-${index}`}>{finding.message}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : (
                <p className="muted">Run validation to inspect structural integrity checks.</p>
              )}
            </article>
          </div>

          <div className="grid cards-2">
            <article className="card">
              <h3>Geometry</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Grids</td>
                    <td>{geometry.grids?.length ?? 0}</td>
                  </tr>
                  <tr>
                    <td>Levels</td>
                    <td>{geometry.levels?.length ?? 0}</td>
                  </tr>
                  <tr>
                    <td>Points</td>
                    <td>{geometry.points?.length ?? 0}</td>
                  </tr>
                  <tr>
                    <td>Lines</td>
                    <td>{geometry.lines?.length ?? 0}</td>
                  </tr>
                  <tr>
                    <td>Areas</td>
                    <td>{geometry.areas?.length ?? 0}</td>
                  </tr>
                </tbody>
              </table>
              {(geometry.levels ?? []).length > 0 ? (
                <ul className="feature-list">
                  {(geometry.levels as Array<{ name: string; elevation: number }>).map((level) => (
                    <li key={level.name}>
                      {level.name} — elevation {level.elevation}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No levels defined yet.</p>
              )}
            </article>

            <article className="card">
              <h3>Materials &amp; sections</h3>
              <ul className="feature-list">
                <li>Concrete: {materials.concrete?.length ?? 0}</li>
                <li>Steel: {materials.steel?.length ?? 0}</li>
                <li>Reinforcement: {materials.reinforcement?.length ?? 0}</li>
                <li>Beam sections: {sections.beams?.length ?? 0}</li>
                <li>Column sections: {sections.columns?.length ?? 0}</li>
                <li>Wall sections: {sections.walls?.length ?? 0}</li>
                <li>Slab sections: {sections.slabs?.length ?? 0}</li>
                <li>Foundation sections: {sections.foundations?.length ?? 0}</li>
              </ul>
            </article>

            <article className="card">
              <h3>Members &amp; supports</h3>
              {members.length === 0 ? (
                <p className="muted">No structural members defined.</p>
              ) : (
                <ul className="feature-list">
                  {(members as Array<{ id: string; name: string; member_type: string }>).map(
                    (member) => (
                      <li key={member.id}>
                        {member.name} ({member.member_type})
                      </li>
                    ),
                  )}
                </ul>
              )}
              <p className="muted">Supports: {supports.length}</p>
            </article>

            <article className="card">
              <h3>Loads</h3>
              <p className="muted">Load cases: {loadCases.length}</p>
              <p className="muted">Load combinations: {loadCombinations.length}</p>
              {(loadCases as Array<{ id: string; name: string; loads?: unknown[] }>).map((lc) => (
                <p key={lc.id}>
                  {lc.name} — {lc.loads?.length ?? 0} load(s)
                </p>
              ))}
            </article>
          </div>

          <div className="grid cards-2">
            <article className="card">
              <h3>Code &amp; units</h3>
              <ul className="feature-list">
                <li>
                  Jurisdiction:{" "}
                  {String((model.code_configuration as { jurisdiction?: string }).jurisdiction ?? "—")}
                </li>
                <li>
                  Building code:{" "}
                  {String(
                    (
                      (model.code_configuration as { governing_building_code?: { edition?: string } })
                        .governing_building_code ?? {}
                    ).edition ?? "—",
                  )}
                </li>
                <li>
                  Unit system:{" "}
                  {String((model.unit_configuration as { system?: string }).system ?? "—")}
                </li>
                <li>
                  Force unit:{" "}
                  {String((model.unit_configuration as { force_unit?: string }).force_unit ?? "—")}
                </li>
              </ul>
            </article>

            <article className="card">
              <h3>Revision history</h3>
              {revisions.length === 0 ? (
                <p className="muted">No revisions recorded yet.</p>
              ) : (
                <ul className="timeline-list">
                  {revisions.slice(0, 8).map((revision) => (
                    <li key={revision.revision_number}>
                      <strong>{getRevisionChangeLabel(revision.change_type)}</strong>
                      <span>{revision.summary}</span>
                      <span className="muted">
                        {formatWorkspaceDate(revision.created_at)}
                        {revision.created_by ? ` · ${revision.created_by}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          </div>

          <article className="card">
            <h3>Version timeline</h3>
            {versions.length === 0 ? (
              <p className="muted">No PEM versions available.</p>
            ) : (
              <ul className="feature-list">
                {versions.map((version) => (
                  <li key={version}>
                    Version {version}
                    {summary.pem_version === version ? " (current)" : ""}
                  </li>
                ))}
              </ul>
            )}
          </article>
        </>
      ) : (
        !loading && <p className="muted">Select a project to view the engineering model.</p>
      )}
    </section>
  );
}
