"use client";

import { BuildingPlanSvg } from "@/components/model/BuildingPlanSvg";
import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  defaultBuildingBrief,
  downloadBuildingSheet,
  generateBuilding,
  getBuilding,
  type BuildingGetResponse,
  type BuildingView,
} from "@/lib/building";
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
  const [brief, setBrief] = useState(defaultBuildingBrief());
  const [building, setBuilding] = useState<BuildingGetResponse | null>(null);
  const [selectedFloorId, setSelectedFloorId] = useState<string>("");
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [generateMessage, setGenerateMessage] = useState<string | null>(null);

  const loadModelData = useCallback(async () => {
    if (!selectedProjectId) {
      setSummary(null);
      setModel(null);
      setValidation(null);
      setVersions([]);
      setRevisions([]);
      setBuilding(null);
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
    try {
      const buildingData = await getBuilding(selectedProjectId);
      setBuilding(buildingData);
      const firstFloor = buildingData.view.floors[0]?.id ?? "";
      setSelectedFloorId(firstFloor);
    } catch {
      setBuilding(null);
    }
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

  async function handleGenerateBuilding() {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    setGenerateMessage(null);
    try {
      const result = await generateBuilding(selectedProjectId, brief);
      if (result.missing_inputs.length) {
        setGenerateMessage(`Need more information: ${result.missing_inputs.join("; ")}`);
      } else {
        setGenerateMessage(
          `Generated v${result.pem_version ?? "—"} (${result.status}). Preliminary automated engineering model — requires review and approval by a qualified engineer.`,
        );
      }
      await loadModelData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Building generation failed");
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
        <h2>Model</h2>
        <p className="subtitle">Review geometry, members, loads, and revisions.</p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      {error ? <div className="alert error">{error}</div> : null}
      {generateMessage ? <div className="alert">{generateMessage}</div> : null}

      {selectedProjectId ? (
        <section className="card">
          <h3>Generate building from brief</h3>
          <p className="muted">
            Deterministic architecture + RC frame + gravity analysis. Not a construction issue set until
            an engineer approves it.
          </p>
          <textarea
            className="input"
            rows={3}
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            aria-label="Building brief"
          />
          <div className="form-row">
            <button
              className="button"
              type="button"
              disabled={busy}
              onClick={() => void handleGenerateBuilding()}
            >
              {busy ? "Generating…" : "Generate building"}
            </button>
          </div>
        </section>
      ) : null}

      {building?.view.site ? (
        <BuildingModelPanel
          building={building}
          selectedFloorId={selectedFloorId}
          selectedElementId={selectedElementId}
          onSelectFloor={setSelectedFloorId}
          onSelectElement={setSelectedElementId}
          onDownloadSheet={(name) => {
            if (!selectedProjectId) return;
            void downloadBuildingSheet(selectedProjectId, name);
          }}
        />
      ) : null}

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
              <details className="meta-summary">
                <summary>Details</summary>
              <ul className="feature-list">
                {formatModelCounts(summary).map((item) => (
                  <li key={item.label}>
                    {item.label}: <strong>{item.value}</strong>
                  </li>
                ))}
              </ul>
              </details>
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

function BuildingModelPanel({
  building,
  selectedFloorId,
  selectedElementId,
  onSelectFloor,
  onSelectElement,
  onDownloadSheet,
}: {
  building: BuildingGetResponse;
  selectedFloorId: string;
  selectedElementId: string | null;
  onSelectFloor: (id: string) => void;
  onSelectElement: (id: string) => void;
  onDownloadSheet: (name: string) => void;
}) {
  const view: BuildingView = building.view;
  const floor = view.floors.find((item) => item.id === selectedFloorId) ?? view.floors[0] ?? null;
  const selectedSpace = floor?.spaces.find((space) => space.id === selectedElementId);
  const selectedColumn = view.columns.find((column) => column.id === selectedElementId);
  const selectedBeam = view.beams.find((beam) => beam.id === selectedElementId);
  const selectedCheck = view.design_checks.find((check) => check.member_id === selectedElementId);

  return (
    <section className="card">
      <h3>Generated building</h3>
      <p className="muted">
        Plot {view.site?.frontage_m} m × {view.site?.depth_m} m · {view.counts.spaces} spaces ·{" "}
        {view.counts.parking} parking · {view.counts.columns} columns · {view.counts.beams} beams ·{" "}
        {view.counts.slabs} slabs · {view.structural_system}
      </p>
      <div className="form-row">
        <select
          className="input"
          value={floor?.id ?? ""}
          onChange={(event) => onSelectFloor(event.target.value)}
          aria-label="Floor plan"
        >
          {view.floors.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} ({item.floor_type})
            </option>
          ))}
        </select>
      </div>
      <BuildingPlanSvg
        view={view}
        floor={floor}
        selectedId={selectedElementId}
        onSelect={onSelectElement}
      />
      <div className="grid cards-2">
        <article>
          <h4>Selected element</h4>
          {selectedSpace ? (
            <p>
              {selectedSpace.name} · {selectedSpace.usage} · {selectedSpace.area_m2.toFixed(2)} m²
            </p>
          ) : selectedColumn ? (
            <p>
              Column {selectedColumn.name}
              {selectedCheck
                ? ` · ${selectedCheck.check_kind} ${selectedCheck.status} (D/C ${selectedCheck.utilization.toFixed(2)})`
                : ""}
            </p>
          ) : selectedBeam ? (
            <p>
              Beam {selectedBeam.name}
              {selectedCheck
                ? ` · ${selectedCheck.check_kind} ${selectedCheck.status} (D/C ${selectedCheck.utilization.toFixed(2)})`
                : ""}
            </p>
          ) : (
            <p className="muted">Click a room, column or beam.</p>
          )}
          <h4>QA</h4>
          {(view.qa_findings ?? []).slice(0, 6).map((finding, index) => (
            <p key={`${finding.code ?? "qa"}-${index}`} className="muted">
              {String(finding.status ?? "")} {String(finding.message ?? finding.code ?? "")}
            </p>
          ))}
        </article>
        <article>
          <h4>Design / analysis</h4>
          <p className="muted">
            {view.disclaimer ??
              "Preliminary automated engineering model — requires review and approval by a qualified engineer."}
          </p>
          <p className="muted">
            Lifecycle: {view.lifecycle_status ?? "—"} · Analysis:{" "}
            {String(view.analysis?.last_analysis_status ?? view.analysis?.solver ?? "—")}
          </p>
          {(view.design_checks ?? []).slice(0, 8).map((check) => (
            <p key={`${check.member_id}-${check.check_kind}`}>
              {check.member_name} {check.check_kind}: {check.status} (D/C {check.utilization.toFixed(2)}) ·{" "}
              {check.code_reference}
            </p>
          ))}
          {(view.story_drifts ?? []).length > 0 ? (
            <>
              <h4>Storey drift</h4>
              {view.story_drifts?.map((drift) => (
                <p key={drift.level_id} className="muted">
                  {drift.story_name}: Δx/h={drift.drift_ratio_x.toFixed(4)} Δy/h={drift.drift_ratio_y.toFixed(4)}{" "}
                  {drift.status}
                </p>
              ))}
            </>
          ) : null}
          {(view.footings ?? []).length > 0 ? (
            <>
              <h4>Foundations</h4>
              {view.footings?.slice(0, 6).map((footing) => (
                <p key={footing.id} className="muted">
                  {footing.id}: {footing.width_m.toFixed(2)}×{footing.length_m.toFixed(2)} m · D/C{" "}
                  {footing.utilization.toFixed(2)} · {footing.status}
                </p>
              ))}
            </>
          ) : null}
          <h4>PDF sheets</h4>
          {building.sheet_names.length === 0 ? (
            <p className="muted">Generate a building to produce PDF sheets.</p>
          ) : (
            building.sheet_names.map((name) => (
              <button
                key={name}
                className="button"
                type="button"
                onClick={() => onDownloadSheet(name)}
              >
                Download {name}
              </button>
            ))
          )}
        </article>
      </div>
    </section>
  );
}
