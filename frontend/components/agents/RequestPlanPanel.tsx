import type { PromptGenerationResult } from "@/lib/api";
import { buildAssistantProfiles } from "@/lib/agent-workspace";

function assistantTitle(agentType: string): string {
  const profile = buildAssistantProfiles([]).find((item) => item.agentType === agentType);
  return profile?.title ?? "Specialist assistant";
}

export function RequestPlanPanel({ plan }: { plan: PromptGenerationResult }) {
  return (
    <div className="plan-panel">
      <p className="result-label">What we understood</p>
      <p className="result-text">{plan.user_intent}</p>

      <p className="result-label">Selected assistant</p>
      <p className="muted">{assistantTitle(plan.selected_agent_type)}</p>

      {plan.missing_information.length > 0 ? (
        <>
          <p className="result-label">Information still needed</p>
          <ul className="plan-list">
            {plan.missing_information.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}

      {plan.execution_plan.length > 0 ? (
        <>
          <p className="result-label">Planned steps</p>
          <ol className="plan-list numbered">
            {plan.execution_plan.map((step) => (
              <li key={step.step_number}>
                <strong>{step.title}</strong>
                <span className="muted"> — {step.description}</span>
              </li>
            ))}
          </ol>
        </>
      ) : null}
    </div>
  );
}
