"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { listProjectFiles, uploadProjectFileWithProgress, type ProjectFileSummary } from "@/lib/api";
import { formatWorkspaceDate, getFileStatusLabel } from "@/lib/workspace";
import { useCallback, useEffect, useRef, useState } from "react";
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
  const [progress, setProgress] = useState<{ name: string; pct: number; index: number; total: number } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
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
      const list = Array.from(selected);
      for (const [i, file] of list.entries()) {
        setProgress({ name: file.name, pct: 0, index: i + 1, total: list.length });
        await uploadProjectFileWithProgress(selectedProjectId, file, (f) =>
          setProgress({ name: file.name, pct: Math.round(f * 100), index: i + 1, total: list.length }),
        );
        await refresh(selectedProjectId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      setProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Documents</p>
        <h2>Project Files</h2>
        <p className="subtitle">Upload drawings, models, and specs for this project.</p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      <section className="card">
        <h3>Upload files</h3>
        <div
          className={dragOver ? "upload-dropzone drag-over" : "upload-dropzone"}
          data-testid="upload-dropzone"
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); void handleUpload(e.dataTransfer.files); }}
        >
          <input
            ref={inputRef}
            id="files-upload-input"
            className="visually-hidden"
            type="file"
            multiple
            disabled={!selectedProjectId || uploading}
            onChange={(event) => void handleUpload(event.target.files)}
          />
          <label
            htmlFor="files-upload-input"
            className="button upload-button"
            aria-disabled={!selectedProjectId || uploading}
          >
            {uploading ? "Uploading…" : "Upload files"}
          </label>
          <p className="muted upload-hint">
            {selectedProjectId ? "or drag and drop files here" : "Select a project above to upload files."}
          </p>
          {progress ? (
            <div className="upload-progress" role="status">
              <span>{progress.total > 1 ? `${progress.index}/${progress.total} · ` : ""}{progress.name} — {progress.pct}%</span>
              <progress max={100} value={progress.pct} />
            </div>
          ) : null}
        </div>
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
