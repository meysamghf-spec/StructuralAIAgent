import type { AssistantProfile } from "@/lib/agent-workspace";

export function AgentOverviewGrid({ assistants }: { assistants: AssistantProfile[] }) {
  return (
    <div className="grid cards-3 agent-grid">
      {assistants.map((assistant) => (
        <article key={assistant.id} className="card agent-card">
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
        </article>
      ))}
    </div>
  );
}
