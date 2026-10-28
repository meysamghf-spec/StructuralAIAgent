import { Suspense } from "react";
import AgentsWorkspaceClient from "./AgentsWorkspaceClient";

function AgentsWorkspaceFallback() {
  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Engineering Assistants</p>
        <h2 className="page-dup-title">Assistants</h2>
        <p className="muted">Loading assistant workspace…</p>
      </header>
    </section>
  );
}

export default function AgentsWorkspacePage() {
  return (
    <Suspense fallback={<AgentsWorkspaceFallback />}>
      <AgentsWorkspaceClient />
    </Suspense>
  );
}
