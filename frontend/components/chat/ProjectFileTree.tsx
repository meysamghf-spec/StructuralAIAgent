"use client";

import Link from "next/link";
import { useRef } from "react";

import type { ProjectFileSummary } from "@/lib/api";
import {
  projectFileAvailabilityLabel,
  projectFileIcon,
} from "@/lib/project-files";

type ProjectFileTreeProps = {
  projectId: string | null;
  files: ProjectFileSummary[];
  loading: boolean;
  error: string | null;
  selectedFileId: string | null;
  onSelectFile: (file: ProjectFileSummary) => void;
  onRetry: () => void;
  onUpload?: (files: FileList) => void;
};

export function ProjectFileTree({
  projectId,
  files,
  loading,
  error,
  selectedFileId,
  onSelectFile,
  onRetry,
  onUpload,
}: ProjectFileTreeProps) {
  const uploadRef = useRef<HTMLInputElement>(null);

  return (
    <div className="project-file-tree" aria-label="Project files">
      <p className="chat-sidebar-label">Files</p>
      {!projectId ? (
        <p className="muted">Select a project to see its files.</p>
      ) : null}
      {projectId && loading ? <p className="muted">⟳ Loading project files...</p> : null}
      {projectId && error ? (
        <div>
          <p className="muted">Unable to load project files.</p>
          <button type="button" className="button secondary" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : null}
      {projectId && !loading && !error && files.length === 0 ? (
        <div>
          <p className="muted">No files in this project yet.</p>
          {onUpload ? (
            <>
              <input
                ref={uploadRef}
                className="sr-only"
                type="file"
                multiple
                onChange={(event) => {
                  if (event.target.files && event.target.files.length > 0) {
                    onUpload(event.target.files);
                    event.target.value = "";
                  }
                }}
              />
              <button
                type="button"
                className="button secondary"
                onClick={() => uploadRef.current?.click()}
              >
                Upload file
              </button>
            </>
          ) : (
            <Link href="/workspace/files" className="chat-sidebar-link">
              Upload file
            </Link>
          )}
        </div>
      ) : null}
      {projectId && !loading && !error && files.length > 0 ? (
        <ul className="project-file-tree-list">
          {files.map((file) => (
            <li key={file.id}>
              <button
                type="button"
                className={
                  file.id === selectedFileId
                    ? "project-file-tree-item is-selected"
                    : "project-file-tree-item"
                }
                onClick={() => onSelectFile(file)}
              >
                <span aria-hidden="true">{projectFileIcon(file.filename, file.file_type)}</span>
                <span className="project-file-tree-name">{file.filename}</span>
                <span className="muted">{projectFileAvailabilityLabel(file)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
