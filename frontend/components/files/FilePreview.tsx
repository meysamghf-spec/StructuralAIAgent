"use client";

import { useEffect, useState } from "react";

import { DxfViewer } from "@/components/cad/DxfViewer";
import { fetchProjectFileBlob, type ProjectFileSummary } from "@/lib/api";
import { previewKind } from "@/lib/file-preview";
import { useUiLang } from "@/hooks/useUiLang";

export function FilePreview({ projectId, file }: { projectId: string; file: ProjectFileSummary }) {
  const { t } = useUiLang();
  const kind = previewKind(file.filename, file.content_type ?? null);
  const [url, setUrl] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let objectUrl: string | null = null;
    setUrl(null);
    setText(null);
    setError(null);
    if (kind === "none") return;
    fetchProjectFileBlob(projectId, file.id)
      .then(async (blob) => {
        if (kind === "dxf" || kind === "text") setText(await blob.text());
        else {
          objectUrl = URL.createObjectURL(kind === "pdf" ? new Blob([blob], { type: "application/pdf" }) : blob);
          setUrl(objectUrl);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, file.id, kind]);
  if (kind === "none") return <p className="muted">{t("No inline preview for this file type.")}</p>;
  if (error) return <p className="alert error">{error}</p>;
  return (
    <div className="file-preview">
      {kind === "image" && url ? <img src={url} alt={file.filename} /> : null}
      {kind === "pdf" && url ? <iframe src={url} title={file.filename} /> : null}
      {kind === "dxf" && text ? <DxfViewer text={text} filename={file.filename} /> : null}
      {kind === "text" && text ? <pre dir="ltr">{text.slice(0, 20000)}</pre> : null}
      {!url && !text ? <p className="muted">{t("Preparing…")}</p> : null}
    </div>
  );
}
