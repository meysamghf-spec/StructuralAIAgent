"use client";

import { useId, useState } from "react";

import { chatT, dirOf, type ChatLang } from "@/lib/chat-i18n";
import type { AgentToolDetail, AgentToolExecution } from "@/lib/chat-types";

type ToolExecutionCardProps = {
  tool: AgentToolExecution;
  lang?: ChatLang | null;
};

function stateSymbol(state: AgentToolExecution["status"]): string {
  if (state === "complete") {
    return "✓";
  }
  if (state === "current") {
    return "⟳";
  }
  if (state === "error") {
    return "✗";
  }
  return "○";
}

function detailRows(tool: AgentToolExecution): AgentToolDetail[] {
  if (tool.details.length > 0) {
    return tool.details;
  }
  return (tool.files ?? []).map((file) => ({
    key: `file:${file.filename}`,
    label:
      file.pageCount != null
        ? `${file.filename} · ${file.pageCount} page${file.pageCount === 1 ? "" : "s"}`
        : file.filename,
    state: file.availability === "failed" ? "error" : tool.status,
  }));
}

export function ToolExecutionCard({ tool, lang = null }: ToolExecutionCardProps) {
  const detailsId = useId();
  const [open, setOpen] = useState(tool.status === "error" || tool.status === "current");
  const rows = detailRows(tool);
  const artifacts = tool.artifacts ?? [];
  const actions = tool.actions ?? [];

  return (
    <section className={`tool-execution-card is-${tool.status}`} aria-label={chatT(lang, tool.name)} dir={dirOf(lang)}>
      <header className="tool-execution-header">
        <div>
          <p className="eyebrow">{chatT(lang, "Agent action")}</p>
          <h3 dir="auto">{chatT(lang, tool.name)}</h3>
        </div>
        <span className={`chat-progress-badge ${tool.status === "error" ? "warning" : ""}`}>
          {chatT(lang, tool.status.replace(/_/g, " "))}
        </span>
      </header>
      {rows.length > 0 ? (
        <ul className="tool-execution-details">
          {rows.map((detail) => (
            <li key={detail.key || detail.label} className={`is-${detail.state}`}>
              <span aria-hidden="true">{stateSymbol(detail.state)}</span>
              <span dir="auto">{chatT(lang, detail.label)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {artifacts.length > 0 ? (
        <ul className="tool-execution-artifacts">
          {artifacts.map((artifact) => (
            <li key={artifact.id}>
              <span aria-hidden="true">✓</span>
              <span dir="auto">{artifact.name}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {tool.error ? (
        <p className="muted tool-execution-error" role="status" dir="auto">
          {chatT(lang, tool.error.reason)}
        </p>
      ) : null}
      {actions.length > 0 || tool.capability ? (
        <div className="tool-execution-toggle">
          {actions.map((action) => (
            <a key={`${action.label}:${action.href}`} href={action.href} className="button secondary">
              {chatT(lang, action.label)}
            </a>
          ))}
          {tool.capability ? (
            <button
              type="button"
              className="button secondary"
              aria-expanded={open}
              aria-controls={detailsId}
              onClick={() => setOpen((value) => !value)}
            >
              {chatT(lang, open ? "Hide details" : "View details")}
            </button>
          ) : null}
        </div>
      ) : null}
      {open && tool.capability ? (
        <p id={detailsId} className="muted tool-execution-capability">
          {chatT(lang, "Capability")}: <bdi dir="ltr">{tool.capability.replace(/_/g, " ")}</bdi>
        </p>
      ) : null}
    </section>
  );
}
