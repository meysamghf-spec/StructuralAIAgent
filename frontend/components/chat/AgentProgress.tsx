"use client";

import type { AgentRunStep } from "@/lib/chat-types";

type AgentProgressProps = {
  steps: AgentRunStep[];
  label?: string;
};

function stateSymbol(state: AgentRunStep["state"]): string {
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

function stateLabel(state: AgentRunStep["state"]): string {
  if (state === "complete") {
    return "Completed";
  }
  if (state === "current") {
    return "In progress";
  }
  if (state === "error") {
    return "Failed";
  }
  return "Pending";
}

export function AgentProgress({ steps, label = "Agent progress" }: AgentProgressProps) {
  if (steps.length === 0) {
    return null;
  }

  const current = steps.find((step) => step.state === "current" || step.state === "error");

  return (
    <ol className="agent-progress" aria-label={label}>
      {steps.map((step) => (
        <li
          key={step.key}
          className={`agent-progress-step is-${step.state}`}
          aria-current={step.state === "current" ? "step" : undefined}
        >
          <span className="agent-progress-marker" aria-hidden="true">
            {stateSymbol(step.state)}
          </span>
          <span className="agent-progress-copy">
            <span className="agent-progress-label">{step.label}</span>
            <span className="agent-progress-state">{stateLabel(step.state)}</span>
          </span>
        </li>
      ))}
      {current ? (
        <span className="visually-hidden">
          Current step: {current.label}, {stateLabel(current.state)}
        </span>
      ) : null}
    </ol>
  );
}
