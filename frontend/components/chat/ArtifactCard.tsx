"use client";

import Link from "next/link";
import { getApiBaseUrl } from "@/lib/api";
import type { EngineeringArtifact } from "@/lib/chat-types";

type ArtifactCardProps = {
  artifact: EngineeringArtifact;
};

function resolveArtifactHref(href: string | null): string | null {
  if (!href) {
    return null;
  }
  if (href.startsWith("/api/")) {
    return `${getApiBaseUrl()}${href}`;
  }
  return href;
}

export function ArtifactCard({ artifact }: ArtifactCardProps) {
  const href = resolveArtifactHref(artifact.href);
  const isDownload = href?.includes("/files/") && href.includes("/content");

  return (
    <article className="artifact-card">
      <div>
        <p className="artifact-card-name">{artifact.name}</p>
        <p className="muted artifact-card-meta">{artifact.artifactType.replace(/_/g, " ")}</p>
        {artifact.description ? <p className="artifact-card-description">{artifact.description}</p> : null}
      </div>
      {href ? (
        isDownload ? (
          <a className="button secondary artifact-card-action" href={href} target="_blank" rel="noreferrer">
            Download
          </a>
        ) : (
          <Link className="button secondary artifact-card-action" href={href}>
            Open
          </Link>
        )
      ) : null}
    </article>
  );
}
