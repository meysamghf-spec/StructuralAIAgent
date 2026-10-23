"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import dynamic from "next/dynamic";

import { Frame3dResultCard } from "@/components/chat/Frame3dResultCard";
import { DownloadsPanel } from "@/components/frame3d/DownloadsPanel";
import { makeT } from "@/lib/frame3d-i18n";
import { projectChatHref } from "@/lib/current-project";
import { apiFetch } from "@/lib/api";
import { mapFrame3dResults } from "@/lib/chat-mappers";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import {
  DEFAULT_FRAME_INPUTS,
  FRAME3D_EVENT,
  FRAME_FORM_FIELDS,
  formToInputs,
  inputsToForm,
  loadFrame3dInputs,
  loadFrame3dPayload,
  saveFrame3dInputs,
  saveFrame3dPayload,
} from "@/lib/frame3d-store";
import { useUiLang } from "@/hooks/useUiLang";
import { hydrateFrame3dFromServer } from "@/lib/chat-runs";

const Frame3dViewer = dynamic(() => import("@/components/chat/Frame3dViewer"), { ssr: false });
const FoundationView = dynamic(() => import("@/components/frame3d/FoundationView"), { ssr: false });

type Mode = "model" | "analysis" | "results" | "design";

export async function runFrame3d(inputs: Record<string, unknown>): Promise<unknown> {
  const res = await apiFetch<{ frame3d_analysis: unknown }>("/api/v1/frame3d/run", {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
  return res.frame3d_analysis;
}

export function Frame3dWorkspacePanel({ mode }: { mode: Mode }) {
  const { lang, t } = useUiLang();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>(inputsToForm(DEFAULT_FRAME_INPUTS));
  const [payload, setPayload] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => {
      const pid = getCurrentProjectId();
      setProjectId(pid);
      setPayload(loadFrame3dPayload(pid));
      const saved = loadFrame3dInputs(pid);
      if (!saved) void hydrateFrame3dFromServer(pid);
      if (saved && mode === "model") setValues(inputsToForm({ ...DEFAULT_FRAME_INPUTS, ...saved }));
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    window.addEventListener(FRAME3D_EVENT, sync);
    return () => {
      window.removeEventListener(PROJECT_EVENT, sync);
      window.removeEventListener(FRAME3D_EVENT, sync);
    };
  }, [mode]);

  async function run(inputs: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const p = await runFrame3d(inputs);
      saveFrame3dInputs(projectId, inputs);
      saveFrame3dPayload(projectId, p);
      setPayload(p);
      setNote(t("Saved to this project."));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if ((mode === "results" || mode === "design") && !payload && !busy && loadFrame3dInputs(projectId)) {
      void run({ ...loadFrame3dInputs(projectId)!, lang });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, payload, projectId]);

  const results = payload ? mapFrame3dResults(payload) : null;
  const saved = loadFrame3dInputs(projectId);
  const groups = Array.from(new Set(FRAME_FORM_FIELDS.map((f) => f.group)));

  return (
    <section className="panel frame3d-panel" dir={lang === "fa" ? "rtl" : "ltr"} lang={lang}>
      <h2>{t("Quick 3D frame model")}</h2>
      <p className="muted">
        {t("Uses the built-in 3D frame solver, Standard 2800, Mabhas 9 design and isolated footings — same engine as the chat.")}
      </p>
      {mode === "model" ? (
        <form
          className="frame3d-form"
          onSubmit={(e) => {
            e.preventDefault();
            void run(formToInputs(values, lang));
          }}
        >
          {groups.map((g) => (
            <fieldset key={g}>
              <legend>{t(g)}</legend>
              {FRAME_FORM_FIELDS.filter((f) => f.group === g).map((f) => (
                <label key={f.key}>
                  <span>
                    {t(f.label)}
                    {f.unit ? ` (${f.unit})` : ""}
                  </span>
                  {f.kind === "select" ? (
                    <select value={values[f.key] ?? ""} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}>
                      {f.options!.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      dir="ltr"
                      inputMode="decimal"
                      value={values[f.key] ?? ""}
                      onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                    />
                  )}
                </label>
              ))}
            </fieldset>
          ))}
          <div className="frame3d-actions">
            <button className="button" type="submit" disabled={busy}>
              {busy ? t("Running…") : t("Run analysis + design")}
            </button>
            <button
              className="button secondary"
              type="button"
              onClick={() => {
                const s = loadFrame3dInputs(projectId);
                if (s) setValues(inputsToForm({ ...DEFAULT_FRAME_INPUTS, ...s }));
                else setNote(t("No chat frame found for this project yet."));
              }}
            >
              {t("Import from last chat frame")}
            </button>
            <button className="button secondary" type="button" onClick={() => setValues(inputsToForm(DEFAULT_FRAME_INPUTS))}>
              {t("Reset to defaults")}
            </button>
          </div>
        </form>
      ) : mode === "analysis" ? (
        <div className="frame3d-actions">
          {saved ? (
            <button className="button" type="button" disabled={busy} onClick={() => void run({ ...saved, lang })}>
              {busy ? t("Running…") : t("Rerun with saved model")}
            </button>
          ) : null}
          <Link className="button secondary" href="/workspace/model">
            {t("Go to Model")}
          </Link>
        </div>
      ) : null}
      {note ? <p className="muted">{note}</p> : null}
      {error ? <p className="alert error">{error}</p> : null}
      {results?.viewer ? (
        <Frame3dViewer data={results.viewer} results={results} t={makeT(results.lang)} embedded />
      ) : null}
      {results?.viewer?.footings.length && (mode === "design" || mode === "results") ? (
        <FoundationView data={results.viewer} qa={results.foundation?.qaKpa ?? 150} t={makeT(results.lang)} />
      ) : null}
      {results || saved ? (
        <DownloadsPanel
          inputs={(results?.inputs as Record<string, unknown> | null) ?? saved}
          projectId={projectId}
          groups={
            mode === "analysis"
              ? ["analysis", "figures", "models"]
              : mode === "design"
                ? ["design", "foundation", "drawings"]
                : mode === "model"
                  ? ["models", "figures"]
                  : undefined
          }
        />
      ) : null}
      {results ? (
        <Frame3dResultCard results={results} downloads={false} />
      ) : mode !== "model" ? (
        <EmptyHint projectId={projectId} />
      ) : null}
    </section>
  );
}

export function EmptyHint({ projectId, text }: { projectId: string | null; text?: string }) {
  const { t } = useUiLang();
  return (
    <div className="empty-state">
      <p>{text ?? t("No 3D frame result yet. Build one on the Model page or describe a frame in the chat.")}</p>
      <p>
        {t("Example prompt")}: <code dir="ltr">3-storey RC frame, 2x2 bays of 5 m, storey height 3.2 m, Standard 2800 high hazard soil II, design per Mabhas 9, foundation</code>
      </p>
      <p>
        <Link className="button" href={projectId ? projectChatHref(projectId) : "/"}>
          {t("Create in chat")}
        </Link>{" "}
        <Link className="button secondary" href="/workspace/model">
          {t("Go to Model")}
        </Link>
      </p>
    </div>
  );
}

/** Latest frame3d result of the current project (payload stored by chat/manual runs; re-run from saved inputs if needed). */
export function useLatestFrame3d() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [payload, setPayload] = useState<unknown>(null);
  const [inputs, setInputs] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const sync = () => {
      const pid = getCurrentProjectId();
      setProjectId(pid);
      const saved = loadFrame3dInputs(pid);
      if (!saved) void hydrateFrame3dFromServer(pid);
      setInputs(saved);
      const p = loadFrame3dPayload(pid);
      setPayload(p);
      if (!p && saved) {
        runFrame3d(saved)
          .then((fresh) => {
            saveFrame3dPayload(pid, fresh);
          })
          .catch((err) => setError(err instanceof Error ? err.message : String(err)));
      }
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    window.addEventListener(FRAME3D_EVENT, sync);
    return () => {
      window.removeEventListener(PROJECT_EVENT, sync);
      window.removeEventListener(FRAME3D_EVENT, sync);
    };
  }, []);
  const results = payload ? mapFrame3dResults(payload) : null;
  return { projectId, payload, inputs: (results?.inputs as Record<string, unknown> | null) ?? inputs, results, error };
}
