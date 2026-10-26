import { apiFetch } from "./api";

export type CadDrawing = {
  id: string;
  project_id: string;
  drawing_type: string;
  output_format: string;
  status: string;
  validation_status: string;
  message: string;
  file_path: string | null;
  layer_summary: Record<string, number>;
  created_at: string;
};

export type CadCapability = {
  software: string;
  availability: string;
  message: string;
};

export async function getAutocadCapability(): Promise<CadCapability> {
  return apiFetch<CadCapability>("/api/v1/cad/capabilities/autocad");
}

export async function generateCadDrawing(payload: {
  project_id: string;
  drawing_type: string;
  output_format: "DXF" | "DWG";
  pem_version?: number;
}): Promise<CadDrawing> {
  return apiFetch<CadDrawing>("/api/v1/cad/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listCadDrawings(projectId: string): Promise<CadDrawing[]> {
  const response = await apiFetch<{ project_id: string; drawings: CadDrawing[] }>(
    `/api/v1/cad/${projectId}/drawings`,
  );
  return Array.isArray(response?.drawings) ? response.drawings : [];
}
