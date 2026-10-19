"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { listProjectFiles, uploadProjectFile, type ProjectFileSummary } from "@/lib/api";
import { formatWorkspaceDate, getFileStatusLabel } from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";
import { FilePreview } from "@/components/files/FilePreview";
import { downloadProjectFile } from "@/lib/api";
import { useUiLang } from "@/hooks/useUiLang";
import Link from "next/link";
import { projectChatHref } from "@/lib/current-project";

export default function FilesWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [files, setFiles] = useState<ProjectFileSummary[]>([]);
  const [uploading, setUploading] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const { t } = useUiLang();

  const refresh = useCallback(async (projectId: string) => {
    if (!projectId) {
      setFiles([]);
      return;
    }
    const response = await listProjectFiles(projectId);
    setFiles(response.files);
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      void refresh(selectedProjectId);
    }
  }, [selectedProjectId, refresh]);

  async function handleUpload(selected: FileList | null) {
    if (!selectedProjectId || !selected?.length) {
      return;
    }
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(selected)) {
        await uploadProjectFile(selectedProjectId, file);
      }
      await refresh(selectedProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Documents</p>
        <h2>Project Files</h2>
        <p className="subtitle">
          Upload drawings, models, spreadsheets, and specifications. The platform handles extraction
          and indexing automatically.
        </p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      <section className="card">
        <h3>Upload files</h3>
        <input
          className="input"
          type="file"
          multiple
          disabled={!selectedProjectId || uploading}
          onChange={(event) => void handleUpload(event.target.files)}
        />
        <p className="muted">
          Supported workflows include PDF, text, and other ingested engineering formats already configured
          in the platform.
        </p>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <h3>Uploaded files</h3>
        {files.length === 0 ? (
          <div className="empty-state">
            <p>{t("No files uploaded yet.")}</p>
            <p>
              {t("Upload above, or attach files in the chat.")}{" "}
              <Link href={selectedProjectId ? projectChatHref(selectedProjectId) : "/"}>{t("Create in chat")}</Link>
            </p>
          </div>
        ) : null}
        <ul className="workspace-list">
          {files.map((file) => (
            <li key={file.id} className="workspace-list-item compact">
              <div>
                <strong>{file.filename}</strong>
                <p className="muted">
                  {getFileStatusLabel(file.extraction_status)} · Uploaded {formatWorkspaceDate(file.upload_time)}
                </p>
                <p>
                  <button type="button" className="link-button" onClick={() => setPreviewId(previewId === file.id ? null : file.id)}>
                    {previewId === file.id ? t("Hide preview") : t("Preview")}
                  </button>{" "}
                  <button type="button" className="link-button" onClick={() => void downloadProjectFile(selectedProjectId, file.id, file.filename)}>
                    {t("Download")}
                  </button>
                </p>
                {previewId === file.id && selectedProjectId ? <FilePreview projectId={selectedProjectId} file={file} /> : null}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
