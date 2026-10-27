"use client";

import { useId, useState } from "react";

import { chatT, dirOf, type ChatLang } from "@/lib/chat-i18n";
import type { AgentRunError } from "@/lib/chat-types";

type AgentErrorCardProps = {
  error: AgentRunError;
  onRetry?: () => void;
  lang?: ChatLang | null;
};

export function AgentErrorCard({ error, onRetry, lang = null }: AgentErrorCardProps) {
  const detailsId = useId();
  const [open, setOpen] = useState(false);

  return (
    <section className="agent-error-card" role="alert" dir={dirOf(lang)}>
      <p className="eyebrow">{chatT(lang, "Agent")}</p>
      <h3>✗ {chatT(lang, error.title)}</h3>
      <p className="muted" dir="auto">{chatT(lang, "Reason")}: {chatT(lang, error.reason)}</p>
      <div className="agent-error-actions">
        <button
          type="button"
          className="button secondary"
          aria-expanded={open}
          aria-controls={detailsId}
          onClick={() => setOpen((value) => !value)}
        >
          {chatT(lang, open ? "Hide details" : "View details")}
        </button>
        {onRetry ? (
          <button type="button" className="button secondary" onClick={onRetry}>
            {chatT(lang, "Try again")}
          </button>
        ) : null}
      </div>
      {open ? (
        <p id={detailsId} className="muted" dir="auto">
          {chatT(lang, error.reason)}
        </p>
      ) : null}
    </section>
  );
}
