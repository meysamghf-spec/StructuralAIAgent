"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { completeAiPrompt } from "@/lib/api";
import { FormEvent, useState } from "react";

export default function AiWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    if (!prompt.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await completeAiPrompt(prompt.trim());
      setAnswer(response.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assistant request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Assistant</p>
        <h2>AI Assistant</h2>
        <p className="subtitle">Ask engineering questions in plain language.</p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
        description="Optional project context can be referenced in your question."
      />

      <section className="card">
        <h3>Ask a question</h3>
        <form className="request-form" onSubmit={handleAsk}>
          <textarea
            className="input request-input"
            rows={4}
            placeholder="Example: What should I review before issuing the lateral system design?"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <button className="button" type="submit" disabled={busy}>
            {busy ? "Thinking…" : "Ask assistant"}
          </button>
        </form>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {answer ? (
        <section className="card">
          <h3>Assistant response</h3>
          <div className="execution-result">
            <p className="result-text">{answer}</p>
          </div>
        </section>
      ) : null}
    </section>
  );
}
