import { apiFetch, getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";

export type BuildingPoint = { x: number; y: number };

export type BuildingSpace = {
  id: string;
  name: string;
  usage: string;
  area_m2: number;
  boundary: BuildingPoint[];
};

export type BuildingFloor = {
  id: string;
  name: string;
  floor_type: string;
  elevation_m: number;
  gross_area_m2: number;
  boundary: BuildingPoint[];
  spaces: BuildingSpace[];
  walls: Array<{ id: string; start: BuildingPoint; end: BuildingPoint }>;
  doors: Array<{ id: string; center: BuildingPoint; width_m: number }>;
  parking_spaces: Array<{ id: string; label: string; area_m2: number; boundary: BuildingPoint[] }>;
};

export type BuildingView = {
  project_name?: string;
  site: {
    frontage_m: number;
    depth_m: number;
    plot_area_m2: number;
    boundary: BuildingPoint[];
    buildable: BuildingPoint[];
  } | null;
  floors: BuildingFloor[];
  stairs: Array<{ id: string; name: string; boundary: BuildingPoint[] }>;
  grid: {
    x_ordinates: number[];
    y_ordinates: number[];
    x_labels: string[];
    y_labels: string[];
  };
  columns: Array<{ id: string; name: string; x: number | null; y: number | null }>;
  beams: Array<{
    id: string;
    name: string;
    start: { x: number; y: number } | null;
    end: { x: number; y: number } | null;
  }>;
  slabs: Array<{ id: string; name: string; boundary: BuildingPoint[] }>;
  load_cases: Array<{ id: string; name: string; category: string; fidelity?: string | null }>;
  design_checks: Array<{
    member_id: string;
    member_name: string;
    check_kind: string;
    demand: number;
    capacity: number;
    utilization: number;
    status: string;
    code_reference: string;
    governing_combination: string;
  }>;
  qa_findings: Array<{ code?: string; message?: string; status?: string; category?: string }>;
  assumptions: unknown[];
  analysis: Record<string, unknown>;
  story_drifts?: Array<{
    level_id: string;
    story_name: string;
    height_m: number;
    drift_ratio_x: number;
    drift_ratio_y: number;
    status: string;
  }>;
  footings?: Array<{
    id: string;
    width_m: number;
    length_m: number;
    utilization: number;
    status: string;
  }>;
  lifecycle_status?: string;
  disclaimer?: string;
  engineering_report?: Record<string, unknown>;
  code_compliance?: Record<string, string>;
  counts: Record<string, number>;
  structural_system?: string;
};

export type BuildingGenerateResponse = {
  project_id: string;
  status: string;
  pem_version: number | null;
  snapshot_id: string | null;
  approval_request_id: string | null;
  drawing_ids: string[];
  sheet_paths: string[];
  missing_inputs: string[];
  summary: Record<string, unknown>;
  view: BuildingView;
};

export type BuildingGetResponse = {
  project_id: string;
  pem_version: number;
  snapshot_id: string;
  view: BuildingView;
  sheet_names: string[];
};

const DEMO_BRIEF =
  "زمین ۱۲×۲۲ متر، بر ۱۲ متر، پیلوت با ۴ پارکینگ، ۳ طبقه مسکونی، هر طبقه یک واحد، هر واحد ۳ خوابه";

export function defaultBuildingBrief(): string {
  return DEMO_BRIEF;
}

export async function generateBuilding(
  projectId: string,
  brief: string,
  options?: { maxIterations?: number; generateDrawings?: boolean },
): Promise<BuildingGenerateResponse> {
  return apiFetch<BuildingGenerateResponse>(`/api/v1/projects/${projectId}/building/generate`, {
    method: "POST",
    body: JSON.stringify({
      brief,
      max_iterations: options?.maxIterations ?? 5,
      generate_drawings: options?.generateDrawings ?? true,
    }),
  });
}

export async function getBuilding(projectId: string): Promise<BuildingGetResponse> {
  return apiFetch<BuildingGetResponse>(`/api/v1/projects/${projectId}/building`);
}

export async function downloadBuildingSheet(projectId: string, sheetName: string): Promise<void> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/projects/${projectId}/building/sheets/${encodeURIComponent(sheetName)}`,
    { headers: getAuthHeaders(), cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Sheet download failed (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = sheetName;
  link.click();
  URL.revokeObjectURL(url);
}

export function spaceFill(usage: string): string {
  switch (usage) {
    case "BEDROOM":
    case "MASTER_BEDROOM":
      return "#1e3a5f";
    case "LIVING":
      return "#164e63";
    case "KITCHEN":
      return "#3f3f1f";
    case "BATHROOM":
    case "WC":
      return "#3b2f4a";
    case "CORRIDOR":
    case "LOBBY":
      return "#1f2937";
    case "STAIR":
    case "ELEVATOR":
      return "#422006";
    case "PARKING":
    case "DRIVE_AISLE":
      return "#1c1917";
    default:
      return "#172554";
  }
}

export function polygonPoints(points: BuildingPoint[]): string {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}
