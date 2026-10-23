/** Helpers for the project file tree — a view over existing project files. */

import type { ProjectFileSummary } from "./api";
import type { ChatAttachment } from "./chat-api";
import type { PendingAttachment } from "./chat";

export type ProjectFileKind =
  | "pdf"
  | "doc"
  | "spreadsheet"
  | "etabs"
  | "sap2000"
  | "dwg"
  | "dxf"
  | "image"
  | "text"
  | "generic";

const KIND_ICONS: Record<ProjectFileKind, string> = {
  pdf: "📄",
  doc: "📄",
  spreadsheet: "📊",
  etabs: "🏗",
  sap2000: "🏗",
  dwg: "📐",
  dxf: "📐",
  image: "🖼",
  text: "📄",
  generic: "📄",
};

const KIND_LABELS: Record<ProjectFileKind, string> = {
  pdf: "PDF",
  doc: "Word document",
  spreadsheet: "Spreadsheet",
  etabs: "ETABS model",
  sap2000: "SAP2000 model",
  dwg: "DWG drawing",
  dxf: "DXF drawing",
  image: "Image",
  text: "Text",
  generic: "File",
};

export function classifyProjectFile(filename: string, fileType?: string | null): ProjectFileKind {
  const extension = filename.toLowerCase().split(".").pop() ?? "";
  if (extension === "pdf") {
    return "pdf";
  }
  if (extension === "doc" || extension === "docx") {
    return "doc";
  }
  if (extension === "xls" || extension === "xlsx" || extension === "csv") {
    return "spreadsheet";
  }
  if (extension === "edb") {
    return "etabs";
  }
  if (extension === "sdb" || extension === "s2k" || extension === "f2k") {
    return "sap2000";
  }
  if (extension === "dwg") {
    return "dwg";
  }
  if (extension === "dxf") {
    return "dxf";
  }
  if (["png", "jpg", "jpeg", "gif", "webp"].includes(extension)) {
    return "image";
  }
  if (extension === "txt") {
    return "text";
  }
  const normalized = (fileType ?? "").toUpperCase();
  if (normalized === "PDF") {
    return "pdf";
  }
  if (normalized === "DOCX") {
    return "doc";
  }
  if (normalized === "SPREADSHEET") {
    return "spreadsheet";
  }
  if (normalized === "IMAGE") {
    return "image";
  }
  if (normalized === "TEXT") {
    return "text";
  }
  return "generic";
}

export function projectFileIcon(filename: string, fileType?: string | null): string {
  return KIND_ICONS[classifyProjectFile(filename, fileType)];
}

export function projectFileTypeLabel(filename: string, fileType?: string | null): string {
  return KIND_LABELS[classifyProjectFile(filename, fileType)];
}

export function projectFileAvailabilityLabel(file: Pick<ProjectFileSummary, "parsing_status" | "extraction_status">): string {
  const extraction = (file.extraction_status ?? "").toUpperCase();
  const parsing = (file.parsing_status ?? "").toUpperCase();
  if (extraction === "FAILED" || parsing === "FAILED") {
    return "Failed";
  }
  if (extraction === "IN_PROGRESS" || parsing === "IN_PROGRESS" || extraction === "PENDING" || parsing === "PENDING") {
    return "Processing";
  }
  if (extraction === "SKIPPED" || parsing === "SKIPPED") {
    return "Stored only";
  }
  if (extraction === "COMPLETE" || parsing === "COMPLETE") {
    return "Available";
  }
  return "Available";
}

export function projectFileToAttachment(file: ProjectFileSummary): ChatAttachment {
  return {
    file_id: file.id,
    filename: file.filename,
    file_type: file.file_type ?? null,
    content_type: file.content_type ?? null,
    status: "ready",
    parsing_status: file.parsing_status ?? null,
    extraction_status: file.extraction_status ?? null,
  };
}

export function attachExistingProjectFile(
  current: PendingAttachment[],
  file: ProjectFileSummary,
): PendingAttachment[] {
  if (current.some((item) => item.uploaded?.file_id === file.id)) {
    return current;
  }
  return [
    ...current,
    {
      localId: `existing-${file.id}`,
      uploaded: projectFileToAttachment(file),
      existingFile: true,
    },
  ];
}

export function projectFileContentPath(projectId: string, fileId: string): string {
  return `/api/v1/projects/${projectId}/files/${fileId}/content`;
}
