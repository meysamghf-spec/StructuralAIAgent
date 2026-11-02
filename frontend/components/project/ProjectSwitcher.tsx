"use client";

import { useEffect, useRef, useState } from "react";

import { NewProjectDialog } from "@/components/project/NewProjectDialog";
import { useProjectScope } from "@/hooks/useProjectScope";
import { useUiLang } from "@/hooks/useUiLang";
import type { ProjectSummary } from "@/lib/api";

type Props = {
  /** "bar": compact button + floating list (top bars). "panel": full-width, list expands inline (sidebars). */
  variant?: "bar" | "panel";
  /** Shared project state from the page (so the chat and the switcher never disagree); falls back to its own. */
  scope?: {
    projects: ProjectSummary[];
    selectedProjectId: string;
    selectedProject: ProjectSummary | null;
    setSelectedProjectId: (id: string) => void;
  };
  disabled?: boolean;
  /** Called after the user picked / created a project (e.g. close a drawer). */
  onChange?: () => void;
};

/** Current project name + the project list + "New project". Switching also switches chat history, model, results… */
export function ProjectSwitcher(props: Props) {
  // useProjectScope loads the list itself; when the page passes its own scope we reuse it instead.
  return props.scope ? <SwitcherView {...props} scope={props.scope} /> : <SelfScoped {...props} />;
}

function SelfScoped(props: Props) {
  const scope = useProjectScope();
  return <SwitcherView {...props} scope={scope} />;
}

function SwitcherView({ variant = "bar", scope, onChange, disabled }: Props & { scope: NonNullable<Props["scope"]> }) {
  const { t } = useUiLang();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: Event) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const current = scope.selectedProject;
  const label = current?.name ?? t("No project selected");

  return (
    <div className={`project-switcher project-switcher-${variant}`} ref={rootRef} data-testid="project-switcher">
      <button
        type="button"
        className="project-switcher-button"
        aria-haspopup="listbox"
        aria-expanded={open}
        title={label}
        disabled={disabled}
        data-testid="project-switcher-button"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="project-switcher-kicker">{t("Project")}</span>
        <span className="project-switcher-name" dir="auto" data-testid="project-switcher-name">{label}</span>
        <span className="project-switcher-caret" aria-hidden="true">▾</span>
      </button>
      {open ? (
        <div className="project-switcher-menu" data-testid="project-switcher-menu">
          <ul role="listbox" aria-label={t("Projects")} className="project-switcher-list">
            {scope.projects.length === 0 ? <li className="muted project-switcher-empty">{t("No projects yet")}</li> : null}
            {scope.projects.map((project) => (
              <li key={project.id} role="option" aria-selected={project.id === scope.selectedProjectId}>
                <button
                  type="button"
                  dir="auto"
                  className={project.id === scope.selectedProjectId ? "project-switcher-item active" : "project-switcher-item"}
                  onClick={() => {
                    if (project.id !== scope.selectedProjectId) scope.setSelectedProjectId(project.id);
                    setOpen(false);
                    onChange?.();
                  }}
                >
                  {project.name}
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="project-switcher-new"
            data-testid="project-switcher-new"
            onClick={() => {
              setOpen(false);
              setCreating(true);
            }}
          >
            ＋ {t("New project")}
          </button>
        </div>
      ) : null}
      <NewProjectDialog open={creating} onClose={() => setCreating(false)} onCreated={() => onChange?.()} />
    </div>
  );
}
