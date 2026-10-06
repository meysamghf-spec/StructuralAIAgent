import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type { ProjectFileSummary } from "../lib/api";
import { buildSendPayload } from "../lib/chat";
import {
  attachExistingProjectFile,
  classifyProjectFile,
  projectFileAvailabilityLabel,
  projectFileContentPath,
  projectFileIcon,
  projectFileToAttachment,
  projectFileTypeLabel,
} from "../lib/project-files";

function sampleFile(overrides: Partial<ProjectFileSummary> = {}): ProjectFileSummary {
  return {
    id: "file-1",
    project_id: "project-1",
    filename: "plans.pdf",
    file_type: "PDF",
    parsing_status: "COMPLETE",
    extraction_status: "COMPLETE",
    upload_time: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("project file classification", () => {
  it("distinguishes real engineering file types from filename and file_type", () => {
    expect(classifyProjectFile("plans.pdf", "PDF")).toBe("pdf");
    expect(classifyProjectFile("spec.docx", "DOCX")).toBe("doc");
    expect(classifyProjectFile("loads.xlsx", "SPREADSHEET")).toBe("spreadsheet");
    expect(classifyProjectFile("model.edb", "UNKNOWN")).toBe("etabs");
    expect(classifyProjectFile("model.sdb", "UNKNOWN")).toBe("sap2000");
    expect(classifyProjectFile("floor1.dwg", "UNKNOWN")).toBe("dwg");
    expect(classifyProjectFile("floor2.dxf", "UNKNOWN")).toBe("dxf");
    expect(classifyProjectFile("photo.png", "IMAGE")).toBe("image");
    expect(classifyProjectFile("notes.txt", "TEXT")).toBe("text");
    expect(projectFileIcon("plans.pdf")).toBe("📄");
    expect(projectFileIcon("loads.xlsx")).toBe("📊");
    expect(projectFileIcon("floor1.dwg")).toBe("📐");
    expect(projectFileTypeLabel("model.edb")).toBe("ETABS model");
  });

  it("uses extraction status for availability and never invents indexing", () => {
    expect(projectFileAvailabilityLabel(sampleFile())).toBe("Available");
    expect(
      projectFileAvailabilityLabel(sampleFile({ extraction_status: "SKIPPED", parsing_status: "SKIPPED" })),
    ).toBe("Stored only");
    expect(projectFileAvailabilityLabel(sampleFile({ extraction_status: "FAILED" }))).toBe("Failed");
    expect(projectFileAvailabilityLabel(sampleFile({ extraction_status: "IN_PROGRESS" }))).toBe("Processing");
  });
});

describe("use in chat reuses the existing file id", () => {
  it("attaches an existing project file without creating a File upload", () => {
    const attached = attachExistingProjectFile([], sampleFile({ id: "abc", filename: "model.edb" }));
    expect(attached).toHaveLength(1);
    expect(attached[0].file).toBeUndefined();
    expect(attached[0].existingFile).toBe(true);
    expect(attached[0].uploaded?.file_id).toBe("abc");
    expect(attached[0].uploaded?.filename).toBe("model.edb");
    const payload = buildSendPayload("Analyze the critical members.", attached);
    expect(payload.attachment_file_ids).toEqual(["abc"]);
  });

  it("does not duplicate an already attached project file", () => {
    const first = attachExistingProjectFile([], sampleFile({ id: "abc" }));
    const second = attachExistingProjectFile(first, sampleFile({ id: "abc" }));
    expect(second).toHaveLength(1);
  });

  it("maps API metadata to a chat attachment reference", () => {
    const attachment = projectFileToAttachment(sampleFile({ id: "file-9", filename: "loads.xlsx" }));
    expect(attachment.file_id).toBe("file-9");
    expect(attachment.status).toBe("ready");
    expect(projectFileContentPath("p1", "file-9")).toBe("/api/v1/projects/p1/files/file-9/content");
  });
});

describe("project file tree UI", () => {
  it("renders real API data and required states without mock files or timers", () => {
    const tree = readFileSync(resolve(__dirname, "../components/chat/ProjectFileTree.tsx"), "utf8");
    expect(tree).toContain("Loading project files");
    expect(tree).toContain("No files in this project yet.");
    expect(tree).toContain("Unable to load project files.");
    expect(tree).toContain("Retry");
    expect(tree).toContain("Upload file");
    expect(tree).toContain("files.map");
    expect(tree).not.toContain("setTimeout");
    expect(tree).not.toContain("mock");
    expect(tree).not.toContain("sample.edb");
  });

  it("sidebar hosts the project file tree and keeps chat-first navigation", () => {
    const sidebar = readFileSync(resolve(__dirname, "../components/chat/ChatSidebar.tsx"), "utf8");
    expect(sidebar).toContain("ProjectFileTree");
    expect(sidebar).toContain("projectId");
    expect(sidebar).toContain('href="/workspace/files"');
    expect(sidebar).toContain("New Project");
  });

  it("workspace selects files, reuses existing ids, and refreshes after upload", () => {
    const workspace = readFileSync(resolve(__dirname, "../components/chat/ChatWorkspace.tsx"), "utf8");
    expect(workspace).toContain("useProjectFiles");
    expect(workspace).toContain("attachExistingProjectFile");
    expect(workspace).toContain("uploadProjectFile");
    expect(workspace).toContain("downloadProjectFile");
    expect(workspace).toContain("setSelectedFile");
    expect(workspace).toContain("setFilesRefreshToken");
    expect(workspace).not.toContain("ProjectFileTreeStore");
    expect(workspace).not.toContain("MockFileService");
  });

  it("context panel shows selected file actions", () => {
    const panel = readFileSync(resolve(__dirname, "../components/chat/ChatContextPanel.tsx"), "utf8");
    expect(panel).toContain("Selected file");
    expect(panel).toContain("Use in chat");
    expect(panel).toContain("Download");
    expect(panel).toContain("selectedFile");
    expect(panel).not.toContain("storage_path");
  });

  it("useChat exposes existing-file attach and does not re-upload those files", () => {
    const hook = readFileSync(resolve(__dirname, "../hooks/useChat.ts"), "utf8");
    expect(hook).toContain("attachExistingProjectFile");
    expect(hook).toContain("uploadConversationAttachment");
  });
});
