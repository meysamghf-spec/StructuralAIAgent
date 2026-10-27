"use client";

import { chatT, dirOf, type ChatLang } from "@/lib/chat-i18n";
import type { AgentRunContext } from "@/lib/chat-types";

type AgentContextStripProps = {
  context: AgentRunContext;
  projectName?: string | null;
  lang?: ChatLang | null;
};

export function AgentContextStrip({ context, projectName, lang = null }: AgentContextStripProps) {
  const items: string[] = [];
  if (context.conversation) {
    items.push(chatT(lang, "Current conversation"));
  }
  if (context.project) {
    items.push(projectName ? chatT(lang, `Project: ${projectName}`) : chatT(lang, "Project context"));
  }
  for (const file of context.files.slice(0, 3)) {
    items.push(file.filename);
  }
  if (context.indexedDocumentCount > 0) {
    items.push(
      chatT(
        lang,
        `${context.indexedDocumentCount} indexed document${context.indexedDocumentCount === 1 ? "" : "s"}`,
      ),
    );
  }
  if (context.capability) {
    items.push(chatT(lang, context.capability));
  }
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="agent-context-strip" aria-label={chatT(lang, "Context used for this response")} dir={dirOf(lang)}>
      <p className="agent-context-heading">{chatT(lang, "Context")}</p>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <span aria-hidden="true">✓</span>
            <span dir="auto">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
