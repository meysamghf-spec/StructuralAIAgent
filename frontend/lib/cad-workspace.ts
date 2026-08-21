const CAD_STATUS_LABELS: Record<string, string> = {
  SUCCESS: "Drawing ready",
  RUNNING: "Generating drawing",
  FAILED: "Generation failed",
  REQUIRES_LOCAL_SOFTWARE: "AutoCAD 2027 is not available on this computer.",
  CREATED: "Queued",
};

const CAD_VALIDATION_LABELS: Record<string, string> = {
  VALIDATED: "Drawing validated",
  INVALID: "Drawing invalid",
  INCOMPLETE: "Drawing incomplete",
  REQUIRES_ENGINEER_REVIEW: "Drawing needs engineering review",
};

export function getCadStatusLabel(status: string): string {
  return CAD_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getCadValidationLabel(status: string): string {
  return CAD_VALIDATION_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getCadNextStep(status: string, outputFormat: string): string {
  if (status === "REQUIRES_LOCAL_SOFTWARE" && outputFormat === "DWG") {
    return "Install AutoCAD 2027 on this computer, or export DXF instead.";
  }
  if (status === "SUCCESS") {
    return "Open the generated drawing from project files or download the exported path.";
  }
  return "Complete the engineering model, then generate the drawing again.";
}

const DRAWING_TYPE_LABELS: Record<string, string> = {
  FRAMING_PLAN: "Framing plan",
  GRID_PLAN: "Grid plan",
  COLUMN_PLAN: "Column plan",
  BEAM_PLAN: "Beam plan",
  SLAB_PLAN: "Slab plan",
  COLUMN_LAYOUT: "Column layout",
  BEAM_LAYOUT: "Beam layout",
  FOUNDATION_LAYOUT: "Foundation layout",
};

export function getDrawingTypeLabel(drawingType: string): string {
  return DRAWING_TYPE_LABELS[drawingType] ?? drawingType.replaceAll("_", " ").toLowerCase();
}
