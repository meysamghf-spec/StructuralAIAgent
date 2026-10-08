import { apiFetch, getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";

export type DrawingSheetIndexItem = {
  sheet_number: string;
  title: string;
  discipline: string;
  availability: string;
  schedule_family: string | null;
  missing_data: string[];
  content_signature: string;
};

export type PendingDrawingSheet = {
  sheet_number: string;
  title: string;
  availability: string;
};

export type DrawingSetIndex = {
  project_id: string;
  pem_snapshot_id: string;
  pem_version: number;
  drawing_set_id: string;
  generated_at: string;
  sheets: DrawingSheetIndexItem[];
  pending_sheets: PendingDrawingSheet[];
  disclaimers: string[];
};

export function sheetAvailabilityLabel(availability: string): string {
  if (availability === "NOT_AVAILABLE") {
    return "Not available in the current PEM";
  }
  if (availability === "PARTIAL") {
    return "Partial — missing values stay marked";
  }
  if (availability === "AVAILABLE") {
    return "Generated from the current PEM";
  }
  if (availability === "NOT_GENERATED") {
    return "Not generated";
  }
  return availability;
}

export function pendingSheetsAreAbsent(
  sheets: { sheet_number: string }[],
  pending: { sheet_number: string; availability: string }[],
): boolean {
  const produced = new Set(sheets.map((sheet) => sheet.sheet_number));
  return pending.every(
    (sheet) => sheet.availability === "NOT_GENERATED" && !produced.has(sheet.sheet_number),
  );
}

export function getDrawingSetIndex(projectId: string): Promise<DrawingSetIndex> {
  return apiFetch<DrawingSetIndex>(`/api/v1/projects/${projectId}/drawing-set`);
}

export async function downloadDrawingSetPdf(projectId: string, pemVersion: number): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/projects/${projectId}/drawing-set/pdf`, {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string" ? body.error.message : `Download failed (${response.status})`;
    throw new Error(message);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = `drawing-set-${projectId}-v${pemVersion}.pdf`;
  link.click();
  URL.revokeObjectURL(objectUrl);
}
