"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { MessageContent } from "@/components/chat/MessageContent";
import { useUiLang } from "@/hooks/useUiLang";
import { useProjectScope } from "@/hooks/useProjectScope";
import { assistantChatHref } from "@/lib/agent-workspace";
import { assistantContext } from "@/lib/assistant-context";
import { agentTypeFromSlug, assistantPageInfo } from "@/lib/assistant-pages";
import { sendChatMessage } from "@/lib/chat-api";

type Turn = { id: number; role: "user" | "assistant"; text: string; hasResultCard?: boolean };

export default function AssistantPageClient({ slug }: { slug: string }) {
  const { lang } = useUiLang();
  const fa = lang === "fa";
  const tx = (en: string, faText: string) => (fa ? faText : en);
  const searchParams = useSearchParams();
  const type = agentTypeFromSlug(slug);
  const info = assistantPageInfo(type);
  const ctx = assistantContext(type);
  const { projects, selectedProjectId, setSelectedProjectId, loading: projectsLoading } = useProjectScope(searchParams.get("project"));

  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const conversationId = useRef<string | undefined>(undefined);
  const nextId = useRef(1);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // A different project means a different conversation scope.
    conversationId.current = undefined;
    setTurns([]);
    setError(null);
  }, [selectedProjectId, type]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [turns.length, busy]);

  const starters = useMemo(() => (ctx ? (fa ? ctx.starters.fa : ctx.starters.en) : []), [ctx, fa]);

  if (!type || !info || !ctx) {
    return (
      <section className="assistant-page" dir={fa ? "rtl" : "ltr"}>
        <h1 className="page-title">{tx("Assistant not found", "دستیار پیدا نشد")}</h1>
        <p className="muted">{tx("This assistant does not exist.", "چنین دستیاری وجود ندارد.")}</p>
        <Link href="/workspace/agents">{tx("← All assistants", "← همهٔ دستیارها")}</Link>
      </section>
    );
  }

  async function send(message: string) {
    const content = message.trim();
    if (!content || busy || !type) return;
    setBusy(true);
    setError(null);
    setText("");
    setTurns((cur) => [...cur, { id: nextId.current++, role: "user", text: content }]);
    try {
      const res = await sendChatMessage({
        message: content,
        assistant: type,
        project_id: selectedProjectId || undefined,
        conversation_id: conversationId.current,
      });
      conversationId.current = res.conversation_id;
      const md = (res.assistant_message.metadata ?? {}) as Record<string, unknown>;
      setTurns((cur) => [
        ...cur,
        {
          id: nextId.current++,
          role: "assistant",
          text: res.assistant_message.content,
          hasResultCard: Boolean(md.engineering_results || md.autocad_result),
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : tx("Request failed", "درخواست ناموفق بود"));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(text);
  }

  const abilities = fa ? info.abilities.fa : info.abilities.en;
  const limits = fa ? info.limits.fa : info.limits.en;

  return (
    <section className="assistant-page" dir={fa ? "rtl" : "ltr"} data-testid="assistant-page">
      <header className="assistant-page-head">
        <Link href="/workspace/agents" className="assistant-page-back">
          {tx("← All assistants", "← همهٔ دستیارها")}
        </Link>
        <h1 className="page-title" data-testid="assistant-page-title">{fa ? ctx.title.fa : ctx.title.en}</h1>
        <p className="subtitle">{fa ? info.description.fa : info.description.en}</p>
      </header>

      <div className="assistant-page-cols">
        <section className="card">
          <h2>{tx("What it can do", "چه کارهایی می‌کند")}</h2>
          <ul className="assistant-page-list">
            {abilities.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
        <section className="card assistant-page-limits" data-testid="assistant-limits">
          <h2>{tx("Limits", "محدودیت‌ها")}</h2>
          <ul className="assistant-page-list">
            {limits.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      </div>

      <section className="card">
        <h2>{tx("Try it", "امتحان کنید")}</h2>
        <label className="muted" htmlFor="assistant-project">{tx("Project", "پروژه")}</label>
        <select
          id="assistant-project"
          className="input project-select"
          value={selectedProjectId}
          onChange={(event) => setSelectedProjectId(event.target.value)}
          disabled={projectsLoading || projects.length === 0}
        >
          {projects.length === 0 ? <option value="">{tx("No projects available", "پروژه‌ای موجود نیست")}</option> : null}
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>

        <div className="assistant-strip-starters" role="group" aria-label={tx("Starter prompts", "پیشنهادهای شروع")}>
          {starters.map((starter) => (
            <button
              key={starter}
              type="button"
              className="button secondary assistant-starter"
              disabled={busy}
              onClick={() => void send(starter)}
            >
              {starter}
            </button>
          ))}
        </div>

        <div className="assistant-chat-log" ref={logRef} aria-live="polite" data-testid="assistant-chat-log">
          {turns.map((turn) => (
            <div key={turn.id} className={`assistant-chat-msg ${turn.role}`}>
              {turn.role === "user" ? turn.text : <MessageContent content={turn.text} />}
              {turn.hasResultCard ? (
                <p className="muted">
                  <Link href={assistantChatHref(type, selectedProjectId)}>
                    {tx("Open the full result card in chat", "کارت کامل نتیجه را در چت باز کنید")}
                  </Link>
                </p>
              ) : null}
            </div>
          ))}
          {busy ? <p className="muted">{tx("Working…", "در حال انجام…")}</p> : null}
        </div>
        {error ? <div className="alert error" role="alert">{error}</div> : null}

        <form className="assistant-chat-form" onSubmit={onSubmit}>
          <textarea
            className="input"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={tx("Ask this assistant…", "از این دستیار بپرسید…")}
            aria-label={tx("Message", "پیام")}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(text);
              }
            }}
          />
          <div className="assistant-page-actions">
            <button className="button" type="submit" disabled={busy || !text.trim()}>
              {tx("Send", "ارسال")}
            </button>{" "}
            <Link className="button secondary" href={assistantChatHref(type, selectedProjectId)}>
              {tx("Open in full chat", "باز کردن در چت کامل")}
            </Link>
          </div>
        </form>
      </section>
    </section>
  );
}
