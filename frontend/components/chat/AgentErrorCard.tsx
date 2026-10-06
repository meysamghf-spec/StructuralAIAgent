"use client";

import { useId, useState } from "react";

import type { AgentRunError } from "@/lib/chat-types";

type AgentErrorCardProps = {
  error: AgentRunError;
  onRetry?: () => void;
};

export function AgentErrorCard({ error, onRetry }: AgentErrorCardProps) {
  const detailsId = useId();
  const [open, setOpen] = useState(false);

  return (
    <section className="agent-error-card" role="alert">
      <p className="eyebrow">Agent</p>
      <h3>✗ {error.title}</h3>
      <p className="muted">Reason: {error.reason}</p>
      <div className="agent-error-actions">
        <button
          type="button"
          className="button secondary"
          aria-expanded={open}
          aria-controls={detailsId}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide details" : "View details"}
        </button>
        {onRetry ? (
          <button type="button" className="button secondary" onClick={onRetry}>
            Try again
          </button>
        ) : null}
      </div>
      {open ? (
        <p id={detailsId} className="muted">
          {error.reason}
        </p>
      ) : null}
    </section>
  );
}
