"use client";

import Link from "next/link";

import { useUiLang } from "@/hooks/useUiLang";
import type { AssistantProfile } from "@/lib/agent-workspace";
import { assistantContext } from "@/lib/assistant-context";
import { assistantPageHref, assistantPageInfo } from "@/lib/assistant-pages";

/**
 * Each assistant card is ONE link to the assistant's own page (whole card clickable, keyboard focusable,
 * no nested links/buttons). Persian labels follow the UI language.
 */
export function AgentOverviewGrid({
  assistants,
  selectedAgentType,
  projectId,
  onSelect,
}: {
  assistants: AssistantProfile[];
  selectedAgentType?: string | null;
  projectId?: string | null;
  onSelect?: (agentType: AssistantProfile["agentType"]) => void;
}) {
  const { lang } = useUiLang();
  const fa = lang === "fa";
  return (
    <div className="grid cards-3 agent-grid" dir={fa ? "rtl" : "ltr"}>
      {assistants.map((assistant) => {
        const info = assistantPageInfo(assistant.agentType);
        const ctx = assistantContext(assistant.agentType);
        const title = ctx ? (fa ? ctx.title.fa : ctx.title.en) : assistant.title;
        const description = fa && info ? info.description.fa : assistant.description;
        const capabilities = info ? (fa ? info.abilities.fa : assistant.capabilities) : assistant.capabilities;
        const selected = Boolean(selectedAgentType && assistant.agentType === selectedAgentType);
        const unavailable = assistant.status !== "Available" || !assistant.agentType;
        const statusLabel = fa ? (unavailable ? "غیرفعال" : "در دسترس") : assistant.status;
        const body = (
          <>
            <span className="agent-card-header">
              <span className="agent-card-title" role="heading" aria-level={3}>{title}</span>
              <span className={`status-pill status-${assistant.status.toLowerCase().replace(" ", "-")}`}>{statusLabel}</span>
            </span>
            <span className="muted agent-description">{description}</span>
            <span className="feature-list agent-capabilities">
              {capabilities.map((capability) => (
                <span key={capability} className="agent-capability">{capability}</span>
              ))}
            </span>
            <span className="agent-card-cta" aria-hidden="true">{fa ? "باز کردن دستیار ←" : "Open assistant →"}</span>
          </>
        );
        if (unavailable) {
          return (
            <div key={assistant.id} className="card agent-card agent-card-disabled" aria-disabled="true">
              {body}
            </div>
          );
        }
        return (
          <Link
            key={assistant.id}
            className={`card agent-card agent-card-link${selected ? " selected" : ""}`}
            href={assistantPageHref(assistant.agentType as string, projectId)}
            data-testid={`assistant-card-${assistant.agentType}`}
            onClick={() => onSelect?.(assistant.agentType)}
          >
            {body}
          </Link>
        );
      })}
    </div>
  );
}
