import WorkspacePlaceholder from "@/components/WorkspacePlaceholder";

export default function AgentsWorkspacePage() {
  return (
    <WorkspacePlaceholder
      title="Agents"
      description="Agent registry, execution history, approval status, and future Meta-Agent workflows. API helpers: listAgents(), listAgentExecutions(projectId)."
    />
  );
}
