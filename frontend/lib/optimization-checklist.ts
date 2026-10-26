/** Prerequisite checklist returned by GET /engineering/optimization/{project}/readiness (bilingual). */
export type ChecklistAction = {
  kind: "link" | "chat" | "auto";
  label: { en: string; fa: string };
  href?: string | null;
  command?: string | null;
};
export type ChecklistStep = {
  key: string;
  done: boolean;
  optional: boolean;
  label: { en: string; fa: string };
  detail: { en: string; fa: string };
  action: ChecklistAction | null;
};
export type OptimizationChecklist = {
  ready: boolean;
  steps: ChecklistStep[];
  missing_keys: string[];
  auto_complete: {
    available: boolean;
    assumptions: { en: string[]; fa: string[] };
    command: { en: string; fa: string };
  };
};

export function isChecklist(value: unknown): value is OptimizationChecklist {
  const v = value as Partial<OptimizationChecklist> | null;
  return !!v && typeof v === "object" && Array.isArray(v.steps) && typeof v.ready === "boolean";
}

/** Chat href that pre-fills the composer with the step's command (the user presses Send). */
export function chatHrefForCommand(command: string, projectId?: string | null): string {
  const q = new URLSearchParams();
  if (projectId) q.set("project", projectId);
  q.set("prompt", command);
  return `/?${q.toString()}`;
}

export function stepAction(step: ChecklistStep, projectId?: string | null): { href: string; label: string } | null {
  return stepActionLang(step, "en", projectId);
}

export function stepActionLang(
  step: ChecklistStep,
  lang: "en" | "fa",
  projectId?: string | null,
): { href: string; label: string } | null {
  const a = step.action;
  if (!a || step.done) return null;
  const label = a.label[lang] || a.label.en;
  if (a.kind === "chat" && a.command) return { href: chatHrefForCommand(a.command, projectId), label };
  if (a.href) return { href: a.href, label };
  if (a.command) return { href: chatHrefForCommand(a.command, projectId), label };
  return null;
}

export function autoCompleteHref(c: OptimizationChecklist, lang: "en" | "fa", projectId?: string | null): string {
  return chatHrefForCommand(`${lang === "fa" ? "بهینه‌سازی قاب" : "optimize the frame"} ; ${c.auto_complete.command[lang]}`, projectId);
}
