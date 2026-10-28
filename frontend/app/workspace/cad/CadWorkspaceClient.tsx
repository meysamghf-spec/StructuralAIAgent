"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  generateCadDrawing,
  getAutocadCapability,
  listCadDrawings,
  type CadCapability,
  type CadDrawing,
} from "@/lib/cad";
import {
  downloadDrawingSetPdf,
  getDrawingSetIndex,
  groupDrawingSet,
  pendingSheetsAreAbsent,
  sheetAvailabilityLabel,
  type DrawingSetIndex,
} from "@/lib/drawing-set";
import {
  getCadNextStep,
  getCadStatusLabel,
  getCadValidationLabel,
  getDrawingTypeLabel,
} from "@/lib/cad-workspace";
import { formatWorkspaceDate } from "@/lib/workspace";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const DRAWING_TYPES = [
  "FRAMING_PLAN",
  "COLUMN_PLAN",
  "BEAM_PLAN",
  "SLAB_PLAN",
  "GRID_PLAN",
  "COLUMN_LAYOUT",
  "BEAM_LAYOUT",
  "FOUNDATION_LAYOUT",
  "SITE_PLAN",
  "PARKING_PLAN",
  "ARCHITECTURAL_FLOOR_PLAN",
  "ROOF_PLAN",
  "ELEVATION",
  "SECTION",
  "COLUMN_SCHEDULE",
  "BEAM_SCHEDULE",
  "SLAB_SCHEDULE",
];

export default function CadWorkspaceClient() {
  const searchParams = useSearchParams();
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope(searchParams.get("project"));
  const [capability, setCapability] = useState<CadCapability | null>(null);
  const [capabilityState, setCapabilityState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [drawings, setDrawings] = useState<CadDrawing[]>([]);
  const [drawingType, setDrawingType] = useState("FRAMING_PLAN");
  const [outputFormat, setOutputFormat] = useState<"DXF" | "DWG">("DXF");
  const [busy, setBusy] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [drawingSet, setDrawingSet] = useState<DrawingSetIndex | null>(null);
  const [drawingSetError, setDrawingSetError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadCadContext = useCallback(async () => {
    setCapabilityState("loading");
    const capabilityPromise = getAutocadCapability()
      .then((capabilityData) => {
        setCapability(capabilityData);
        setCapabilityState("ready");
      })
      .catch(() => {
        setCapability(null);
        setCapabilityState("unavailable");
      });
    if (!selectedProjectId) {
      setDrawings([]);
      setDrawingSet(null);
      setDrawingSetError(null);
      setHistoryError(null);
      await capabilityPromise;
      return;
    }
    await Promise.all([
      capabilityPromise,
      listCadDrawings(selectedProjectId).then(
        (drawingData) => {
          setDrawings(drawingData);
          setHistoryError(null);
        },
        (err: unknown) => {
          setDrawings([]);
          setHistoryError(err instanceof Error ? err.message : "CAD history could not be loaded");
        },
      ),
      getDrawingSetIndex(selectedProjectId).then(
        (drawingSetData) => {
          setDrawingSet(drawingSetData);
          setDrawingSetError(null);
        },
        (err: unknown) => {
          setDrawingSet(null);
          setDrawingSetError(err instanceof Error ? err.message : "PEM drawing set could not be loaded");
        },
      ),
    ]);
  }, [selectedProjectId]);

  useEffect(() => {
    async function load() {
      try {
        await loadCadContext();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load CAD workspace");
      }
    }
    void load();
  }, [loadCadContext, setError]);

  async function handleGenerate() {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const drawing = await generateCadDrawing({
        project_id: selectedProjectId,
        drawing_type: drawingType,
        output_format: outputFormat,
      });
      setMessage(drawing.message);
      await loadCadContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Drawing generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workspace-page">
      <header className="page-header">
        <p className="eyebrow">CAD</p>
        <h2 className="page-dup-title">CAD</h2>
        <p className="subtitle">Check AutoCAD capability and drawing sets.</p>
      </header>
      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
        description="The PEM drawing set is generated from the current project snapshot. A separate CAD export can be DXF without AutoCAD."
      />

      {error ? <p className="workspace-error">{error}</p> : null}
      {message ? <p className="workspace-note">{message}</p> : null}

      <section className="workspace-card">
        <h2>AutoCAD capability</h2>
        {capability ? (
          <>
            <p>{capability.message}</p>
            <p className="workspace-meta">
              Status: {capability.availability === "AVAILABLE" ? "Available" : "Not available on this computer"}
            </p>
          </>
        ) : (
          <p>
            {capabilityState === "loading"
              ? "Checking AutoCAD availability…"
              : "AutoCAD status was not loaded. DXF export and the PEM drawing set do not require it."}
          </p>
        )}
      </section>

      <section className="workspace-card" aria-label="PEM drawing set">
        <h2>Drawing set from the current PEM</h2>
        {drawingSetError ? <p className="workspace-error">{drawingSetError}</p> : null}
        {drawingSet && drawingSet.project_id === selectedProjectId ? (
          <>
            <p className="workspace-meta">
              PEM version {drawingSet.pem_version} · snapshot {drawingSet.pem_snapshot_id}
            </p>
            <DrawingSetGroupsView index={drawingSet} />
            <button
              type="button"
              disabled={pdfBusy}
              onClick={() => {
                setPdfBusy(true);
                setError(null);
                void downloadDrawingSetPdf(drawingSet.project_id, drawingSet.pem_version)
                  .catch((err: unknown) => {
                    setError(err instanceof Error ? err.message : "Drawing set download failed");
                  })
                  .finally(() => setPdfBusy(false));
              }}
            >
              {pdfBusy ? "Preparing PDF…" : "Download drawing set PDF"}
            </button>
          </>
        ) : drawingSetError ? null : selectedProjectId ? (
          <p>Reading the current PEM drawing set…</p>
        ) : (
          <p>Select a project to read its PEM drawing set.</p>
        )}
      </section>

      <section className="workspace-card">
        <h2>Generate drawing</h2>
        <div className="workspace-form-row">
          <label>
            Drawing type
            <select value={drawingType} onChange={(event) => setDrawingType(event.target.value)}>
              {DRAWING_TYPES.map((type) => (
                <option key={type} value={type}>
                  {getDrawingTypeLabel(type)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Format
            <select
              value={outputFormat}
              onChange={(event) => setOutputFormat(event.target.value as "DXF" | "DWG")}
            >
              <option value="DXF">DXF</option>
              <option value="DWG">DWG</option>
            </select>
          </label>
        </div>
        <button type="button" disabled={!selectedProjectId || busy} onClick={() => void handleGenerate()}>
          {busy ? "Generating…" : "Generate drawing"}
        </button>
        <p className="workspace-help">
          {outputFormat === "DWG"
            ? "DWG export requires AutoCAD 2027 on this computer."
            : "DXF is generated directly from model geometry — no AutoCAD required."}
        </p>
      </section>

      <section className="workspace-card">
        <h2>Drawing history</h2>
        {historyError ? <p className="workspace-error">{historyError}</p> : null}
        {historyError ? null : drawings.length === 0 ? (
          <p>No drawings yet. Generate a framing, column, beam, or slab plan to get started.</p>
        ) : (
          <ul className="workspace-list">
            {drawings.map((drawing) => (
              <li key={drawing.id} className="workspace-list-item">
                <div>
                  <strong>{getDrawingTypeLabel(drawing.drawing_type)}</strong> ({drawing.output_format})
                </div>
                <div>{getCadStatusLabel(drawing.status)}</div>
                <div>{getCadValidationLabel(drawing.validation_status)}</div>
                <div className="workspace-meta">{formatWorkspaceDate(drawing.created_at)}</div>
                <div className="workspace-help">{getCadNextStep(drawing.status, drawing.output_format)}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function DrawingSetGroupsView({ index }: { index: DrawingSetIndex }) {
  const groups = groupDrawingSet(index);
  return (
    <>
      <SheetGroup title="Schedules" sheets={groups.schedules} />
      <SheetGroup title="Structural sheets" sheets={groups.structural} />
      <SheetGroup title="Architectural sheets" sheets={groups.architectural} />
      {pendingSheetsAreAbsent(index.sheets, groups.pending) ? (
        <div>
          <h3>Not generated</h3>
          <ul className="workspace-list">
            {groups.pending.map((sheet) => (
              <li key={sheet.sheet_number} className="workspace-list-item">
                <strong>
                  {sheet.sheet_number} {sheet.title}
                </strong>
                <div>{sheetAvailabilityLabel(sheet.availability)}</div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}

function SheetGroup({ title, sheets }: { title: string; sheets: DrawingSetIndex["sheets"] }) {
  if (sheets.length === 0) {
    return null;
  }
  return (
    <div>
      <h3>{title}</h3>
      <ul className="workspace-list">
        {sheets.map((sheet) => (
          <li key={sheet.sheet_number} className="workspace-list-item">
            <strong>
              {sheet.sheet_number} {sheet.title}
            </strong>
            <div>{sheetAvailabilityLabel(sheet.availability)}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
