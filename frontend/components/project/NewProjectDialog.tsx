"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";

import { useUiLang } from "@/hooks/useUiLang";
import type { ProjectSummary } from "@/lib/api";
import { cleanProjectName, createProjectAndSwitch, PROJECT_NAME_MAX } from "@/lib/project-actions";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Called after the project exists and is the active project (chat / pages already follow it). */
  onCreated?: (project: ProjectSummary) => void;
};

/** "New project": asks for a name, creates the project, switches the whole app to it. */
export function NewProjectDialog({ open, onClose, onCreated }: Props) {
  const { lang, t } = useUiLang();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setName("");
      setError(null);
      setBusy(false);
      const id = window.setTimeout(() => inputRef.current?.focus(), 30);
      return () => window.clearTimeout(id);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  if (!open) return null;

  const clean = cleanProjectName(name);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!clean) {
      setError(t("Enter a project name."));
      inputRef.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const project = await createProjectAndSwitch(clean);
      onCreated?.(project);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Could not create the project."));
      setBusy(false);
    }
  }

  // Portal: drawers use transforms, which would otherwise trap a fixed overlay inside the drawer.
  return createPortal(
    <div
      className="np-backdrop"
      data-testid="new-project-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <form
        className="np-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="np-title"
        dir={lang === "fa" ? "rtl" : "ltr"}
        data-testid="new-project-dialog"
        onSubmit={submit}
      >
        <h2 id="np-title" className="np-title">{t("New project")}</h2>
        <label className="np-label" htmlFor="np-name">{t("Project name")}</label>
        <input
          id="np-name"
          ref={inputRef}
          className="input np-input"
          dir="auto"
          value={name}
          maxLength={PROJECT_NAME_MAX}
          placeholder={t("e.g. Arak office building")}
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          data-testid="new-project-name"
          onChange={(event) => {
            setName(event.target.value);
            if (error) setError(null);
          }}
        />
        <p className="np-hint muted">{t("A new project starts with an empty chat, model, analysis, design and reports.")}</p>
        {error ? <p className="alert error np-error" role="alert" data-testid="new-project-error">{error}</p> : null}
        <div className="np-actions">
          <button type="button" className="button secondary" onClick={onClose} disabled={busy} data-testid="new-project-cancel">
            {t("Cancel")}
          </button>
          <button type="submit" className="button" disabled={busy || !clean} data-testid="new-project-create">
            {busy ? t("Creating…") : t("Create project")}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}
