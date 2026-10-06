"use client";

import type { AgentRunContext } from "@/lib/chat-types";

type AgentContextStripProps = {
  context: AgentRunContext;
  projectName?: string | null;
};

export function AgentContextStrip({ context, projectName }: AgentContextStripProps) {
  const items: string[] = [];
  if (context.conversation) {
    items.push("Current conversation");
  }
  if (context.project) {
    items.push(projectName ? `Project: ${projectName}` : "Project context");
  }
  for (const file of context.files.slice(0, 3)) {
    items.push(file.filename);
  }
  if (context.indexedDocumentCount > 0) {
    items.push(
      `${context.indexedDocumentCount} indexed document${context.indexedDocumentCount === 1 ? "" : "s"}`,
    );
  }
  if (context.capability) {
    items.push(context.capability);
  }
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="agent-context-strip" aria-label="Context used for this response">
      <p className="agent-context-heading">Context</p>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <span aria-hidden="true">✓</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
