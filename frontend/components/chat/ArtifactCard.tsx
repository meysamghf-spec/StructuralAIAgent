"use client";

import Link from "next/link";
import { getApiBaseUrl } from "@/lib/api";
import { chatT, dirOf, type ChatLang } from "@/lib/chat-i18n";
import type { EngineeringArtifact } from "@/lib/chat-types";

type ArtifactCardProps = {
  artifact: EngineeringArtifact;
  lang?: ChatLang | null;
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

export function ArtifactCard({ artifact, lang = null }: ArtifactCardProps) {
  const href = resolveArtifactHref(artifact.href);
  const isDownload = href?.includes("/files/") && href.includes("/content");

  return (
    <article className="artifact-card" dir={dirOf(lang)}>
      <div>
        <p className="artifact-card-name" dir="auto">{artifact.name}</p>
        <p className="muted artifact-card-meta">{artifact.artifactType.replace(/_/g, " ")}</p>
        {artifact.description ? <p className="artifact-card-description" dir="auto">{artifact.description}</p> : null}
      </div>
      {href ? (
        isDownload ? (
          <a className="button secondary artifact-card-action" href={href} target="_blank" rel="noreferrer">
            {chatT(lang, "Download")}
          </a>
        ) : (
          <Link className="button secondary artifact-card-action" href={href}>
            {chatT(lang, "Open")}
          </Link>
        )
      ) : null}
    </article>
  );
}
