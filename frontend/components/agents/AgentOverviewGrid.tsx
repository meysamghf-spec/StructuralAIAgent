import Link from "next/link";

import { assistantChatHref, type AssistantProfile } from "@/lib/agent-workspace";

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
  return (
    <div className="grid cards-3 agent-grid">
      {assistants.map((assistant) => (
        <article
          key={assistant.id}
          className={`card agent-card${selectedAgentType && assistant.agentType === selectedAgentType ? " selected" : ""}`}
        >
          <div className="agent-card-header">
            <h3>{assistant.title}</h3>
            <span className={`status-pill status-${assistant.status.toLowerCase().replace(" ", "-")}`}>
              {assistant.status}
            </span>
          </div>
          <p className="muted agent-description">{assistant.description}</p>
          <ul className="feature-list agent-capabilities">
            {assistant.capabilities.map((capability) => (
              <li key={capability}>{capability}</li>
            ))}
          </ul>
          {assistant.agentType ? (
            assistant.status === "Available" ? (
              <Link
                className="button secondary"
                href={assistantChatHref(assistant.agentType, projectId)}
                onClick={() => onSelect?.(assistant.agentType)}
              >
                Use this assistant
              </Link>
            ) : (
              <button className="button secondary" type="button" disabled>
                Unavailable
              </button>
            )
          ) : null}
        </article>
      ))}
    </div>
  );
}
