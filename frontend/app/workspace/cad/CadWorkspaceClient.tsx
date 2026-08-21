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
  getCadNextStep,
  getCadStatusLabel,
  getCadValidationLabel,
  getDrawingTypeLabel,
} from "@/lib/cad-workspace";
import { formatWorkspaceDate } from "@/lib/workspace";
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
];

export default function CadWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [capability, setCapability] = useState<CadCapability | null>(null);
  const [drawings, setDrawings] = useState<CadDrawing[]>([]);
  const [drawingType, setDrawingType] = useState("FRAMING_PLAN");
  const [outputFormat, setOutputFormat] = useState<"DXF" | "DWG">("DXF");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadCadContext = useCallback(async () => {
    const capabilityData = await getAutocadCapability();
    setCapability(capabilityData);
    if (!selectedProjectId) {
      setDrawings([]);
      return;
    }
    const drawingData = await listCadDrawings(selectedProjectId);
    setDrawings(drawingData);
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
      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
        description="Generate engineering drawings from your validated model. DXF export works without AutoCAD."
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
          <p>Checking AutoCAD availability…</p>
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
        {drawings.length === 0 ? (
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
