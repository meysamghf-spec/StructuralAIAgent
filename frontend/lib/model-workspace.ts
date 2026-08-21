const ANALYSIS_STATUS_LABELS: Record<string, string> = {
  NOT_CONFIGURED: "Not configured",
  PARTIAL: "Partially configured",
  READY_FOR_ANALYSIS_ENGINE: "Ready for analysis engine",
};

const MODEL_SECTION_LABELS: Record<string, string> = {
  geometry: "Geometry",
  materials: "Materials",
  sections: "Sections",
  members: "Members",
  supports: "Supports",
  load_cases: "Load cases",
  load_combinations: "Load combinations",
  analysis_model: "Analysis model",
  design_parameters: "Design parameters",
};

const REVISION_CHANGE_LABELS: Record<string, string> = {
  GEOMETRY_UPDATE: "Geometry updated",
  MATERIALS_UPDATE: "Materials updated",
  SECTIONS_UPDATE: "Sections updated",
  MEMBERS_UPDATE: "Members updated",
  SUPPORTS_UPDATE: "Supports updated",
  LOADS_UPDATE: "Loads updated",
  LOAD_COMBINATIONS_UPDATE: "Load combinations updated",
  ANALYSIS_MODEL_UPDATE: "Analysis model updated",
  DESIGN_PARAMETERS_UPDATE: "Design parameters updated",
  PEM_UPDATE: "Model updated",
};

export function getAnalysisStatusLabel(status: string): string {
  return ANALYSIS_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getModelSectionLabel(key: string): string {
  return MODEL_SECTION_LABELS[key] ?? key.replaceAll("_", " ");
}

export function getRevisionChangeLabel(changeType: string): string {
  return REVISION_CHANGE_LABELS[changeType] ?? changeType.replaceAll("_", " ").toLowerCase();
}

export function formatModelCounts(summary: {
  grid_count: number;
  level_count: number;
  material_count: number;
  section_count: number;
  member_count: number;
  support_count: number;
  load_case_count: number;
  load_combination_count: number;
}): Array<{ label: string; value: number }> {
  return [
    { label: "Grids", value: summary.grid_count },
    { label: "Levels", value: summary.level_count },
    { label: "Materials", value: summary.material_count },
    { label: "Sections", value: summary.section_count },
    { label: "Members", value: summary.member_count },
    { label: "Supports", value: summary.support_count },
    { label: "Load cases", value: summary.load_case_count },
    { label: "Combinations", value: summary.load_combination_count },
  ];
}
