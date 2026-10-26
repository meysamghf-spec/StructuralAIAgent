"use client";

import Link from "next/link";

import { useUiLang } from "@/hooks/useUiLang";
import {
  autoCompleteHref,
  stepActionLang,
  type OptimizationChecklist as Checklist,
} from "@/lib/optimization-checklist";

export function OptimizationChecklist({ checklist, projectId }: { checklist: Checklist; projectId?: string | null }) {
  const { lang } = useUiLang();
  const l = lang === "fa" ? "fa" : "en";
  const missing = checklist.steps.filter((s) => !s.done && !s.optional).length;
  return (
    <div className="optimization-checklist" data-testid="optimization-checklist" dir={l === "fa" ? "rtl" : "ltr"}>
      <h4>
        {checklist.ready
          ? l === "fa" ? "همه پیش‌نیازها آماده است" : "All prerequisites are met"
          : l === "fa" ? `${missing} مرحله باید تکمیل شود` : `${missing} step${missing === 1 ? "" : "s"} still to complete`}
      </h4>
      <ol className="checklist-steps">
        {checklist.steps.map((s) => {
          const act = stepActionLang(s, l, projectId);
          return (
            <li key={s.key} className={`checklist-step ${s.done ? "done" : s.optional ? "optional" : "missing"}`}>
              <span aria-hidden="true" className="checklist-mark">{s.done ? "✅" : s.optional ? "➖" : "❌"}</span>
              <div>
                <strong>{s.label[l]}</strong>
                <div className="muted">{s.detail[l]}</div>
                {act ? <Link className="button secondary small" href={act.href}>{act.label}</Link> : null}
              </div>
            </li>
          );
        })}
      </ol>
      {checklist.auto_complete.available ? (
        <details className="checklist-auto">
          <summary>{l === "fa" ? "تکمیل خودکار با پیش‌فرض‌ها (فرض‌ها را ببینید)" : "Auto-complete with defaults (see assumptions)"}</summary>
          <ul>
            {checklist.auto_complete.assumptions[l].map((a) => <li key={a}>{a}</li>)}
          </ul>
          <Link className="button" href={autoCompleteHref(checklist, l, projectId)}>
            {l === "fa" ? "تکمیل خودکار در چت" : "Auto-complete in chat"}
          </Link>
        </details>
      ) : null}
    </div>
  );
}
