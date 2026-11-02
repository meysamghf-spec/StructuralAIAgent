"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import dynamic from "next/dynamic";

import { Frame3dDesignCard, Frame3dResultCard } from "@/components/chat/Frame3dResultCard";
import { SectionErrorBoundary } from "@/components/common/SectionErrorBoundary";
import { DownloadsPanel } from "@/components/frame3d/DownloadsPanel";
import { makeT } from "@/lib/frame3d-i18n";
import { projectChatHref } from "@/lib/current-project";
import { ensureCurrentProject } from "@/lib/ensure-project";
import { runFrame3d } from "@/lib/frame3d-run";
import { FrameModelForm } from "@/components/frame3d/FrameModelForm";
import { MissingInputsForm } from "@/components/frame3d/MissingInputsForm";
import { mapFrame3dResults } from "@/lib/chat-mappers";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import {
  DEFAULT_FRAME_INPUTS,
  FRAME3D_EVENT,
  inputsToForm,
  loadFrame3dInputs,
  loadFrame3dPayload,
  saveFrame3dInputs,
  saveFrame3dPayload,
} from "@/lib/frame3d-store";
import { missingGeometry } from "@/lib/input-labels";
import { useUiLang } from "@/hooks/useUiLang";
import { hydrateFrame3dFromServer, incompleteFrameRun, listProjectChatRuns } from "@/lib/chat-runs";

const Frame3dViewer = dynamic(() => import("@/components/chat/Frame3dViewer"), { ssr: false });
const FoundationView = dynamic(() => import("@/components/frame3d/FoundationView"), { ssr: false });

type Mode = "model" | "results" | "design" | "foundation";

export { runFrame3d };

export function isIncompleteFramePayload(payload: unknown): boolean {
  const p = payload as { status?: string; missing_inputs?: unknown[] } | null;
  return !!p && typeof p === "object" && p.status === "MISSING_REQUIRED_INPUT" && Array.isArray(p.missing_inputs) && p.missing_inputs.length > 0
    && !p.missing_inputs.includes("frame_model");
}

export function incompleteInputs(payload: unknown): Record<string, unknown> | null {
  const p = payload as { inputs?: Record<string, unknown> } | null;
  return p && p.inputs && typeof p.inputs === "object" ? p.inputs : null;
}

export function Frame3dWorkspacePanel({ mode }: { mode: Mode }) {
  return (
    <SectionErrorBoundary label="3D frame workspace">
      <Frame3dWorkspacePanelInner mode={mode} />
    </SectionErrorBoundary>
  );
}

function Frame3dWorkspacePanelInner({ mode }: { mode: Mode }) {
  const { lang, t } = useUiLang();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>(inputsToForm(DEFAULT_FRAME_INPUTS));
  const [payload, setPayload] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Changes when saved inputs appear (e.g. restored from the latest chat run) so the re-run effect below fires.
  const [savedKey, setSavedKey] = useState("");

  useEffect(() => {
    const sync = () => {
      const pid = getCurrentProjectId();
      if (!pid) void ensureCurrentProject();
      setProjectId(pid);
      setError(null);
      setNote(null);
      setPayload(loadFrame3dPayload(pid));
      const saved = loadFrame3dInputs(pid);
      setSavedKey(saved ? JSON.stringify(saved) : "");
      if (!saved) {
        void hydrateFrame3dFromServer(pid);
        // Results: a chat run that stopped for missing inputs is completed right here (one section, no second card).
        if (mode === "results" && pid) {
          void listProjectChatRuns(pid)
            .then((runs) => {
              const run = incompleteFrameRun(runs);
              const missing = run?.inputs ? missingGeometry(run.inputs) : [];
              if (!run?.inputs || missing.length === 0 || loadFrame3dPayload(pid)) return;
              setPayload({ status: "MISSING_REQUIRED_INPUT", missing_inputs: missing, inputs: run.inputs });
            })
            .catch(() => undefined);
        }
      }
      // A project without saved inputs shows the defaults, never the previous project's form values.
      if (mode === "model") setValues(inputsToForm({ ...DEFAULT_FRAME_INPUTS, ...(saved ?? {}) }));
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    window.addEventListener(FRAME3D_EVENT, sync);
    return () => {
      window.removeEventListener(PROJECT_EVENT, sync);
      window.removeEventListener(FRAME3D_EVENT, sync);
    };
  }, [mode]);

  async function run(inputs: Record<string, unknown>, assumeDefaults = false) {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const p = await runFrame3d(inputs, assumeDefaults);
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
    if ((mode === "results" || mode === "design" || mode === "foundation") && !payload && !busy && loadFrame3dInputs(projectId)) {
      void run({ ...loadFrame3dInputs(projectId)!, lang });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, payload, projectId, savedKey]);

  const incomplete = isIncompleteFramePayload(payload);
  const results = payload ? mapFrame3dResults(payload) : null;
  const saved = loadFrame3dInputs(projectId);

  return (
    <section className="panel frame3d-panel" dir={lang === "fa" ? "rtl" : "ltr"} lang={lang}>
      <h2>{mode === "foundation" ? t("Foundation design") : mode === "design" ? t("Member design") : t("Quick 3D frame model")}</h2>
      <p className="muted">
        {mode === "design"
          ? t("Mabhas 9 RC beam and column design (D/C, rebar, strong column / weak beam) from the latest 3D frame run, same engine as the chat.")
          : t("Uses the built-in 3D frame solver, Standard 2800, Mabhas 9 design and isolated footings — same engine as the chat.")}
      </p>
      {mode === "design" ? (
        <p className="muted" data-testid="design-related-links">
          {t("Related:")} <Link href="/workspace/results">{t("Results")}</Link> · <Link href="/workspace/foundation">{t("Foundation")}</Link> ·{" "}
          <Link href="/workspace/analysis">{t("Analysis")}</Link>
        </p>
      ) : null}
      {incomplete ? (
        <div className="frame3d-repair" data-testid="frame3d-repair">
          <strong>{t("This model is incomplete")}</strong>
          <p className="muted" style={{ margin: "0.3rem 0" }}>
            {t("Some required inputs are missing. I can complete them with typical values (4 storeys, 3×3 bays of 5 m, 3.2 m storey height, Iranian codes) and re-run; the assumptions are listed in the result.")}
          </p>
          <MissingInputsForm
            inputs={incompleteInputs(payload) ?? saved}
            projectId={projectId}
            keys={missingGeometry(incompleteInputs(payload) ?? saved ?? {})}
            onDone={(p) => setPayload(p)}
          />
          <button
            className="button secondary"
            type="button"
            disabled={busy}
            onClick={() => void run({ ...((incompleteInputs(payload) ?? {}) as Record<string, unknown>), lang }, true)}
          >
            {t("Complete with defaults and run")}
          </button>
        </div>
      ) : null}
      {mode === "model" ? (
        <FrameModelForm
          values={values}
          setValues={setValues}
          busy={busy}
          onRun={(inputs) => void run(inputs)}
          onImport={() => {
            const s = loadFrame3dInputs(projectId);
            if (s) setValues(inputsToForm({ ...DEFAULT_FRAME_INPUTS, ...s }));
            else setNote(t("No chat frame found for this project yet."));
          }}
        />
      ) : null}
      {note ? <p className="muted">{note}</p> : null}
      {error ? <p className="alert error">{error}</p> : null}
      {results?.viewer && mode !== "foundation" && mode !== "design" ? (
        <SectionErrorBoundary label="3D viewer">
          <Frame3dViewer data={results.viewer} results={results} t={makeT(results.lang)} embedded />
        </SectionErrorBoundary>
      ) : null}
      {results?.viewer?.footings?.length && (mode === "results" || mode === "foundation") ? (
        <SectionErrorBoundary label="Foundation">
          <FoundationView data={results.viewer} qa={results.foundation?.qaKpa ?? 150} t={makeT(results.lang)} />
        </SectionErrorBoundary>
      ) : null}
      {results || saved ? (
        <DownloadsPanel
          inputs={(results?.inputs as Record<string, unknown> | null) ?? saved}
          projectId={projectId}
          groups={
            mode === "design"
              ? ["design", "drawings"]
              : mode === "foundation"
                ? ["foundation", "drawings"]
                : mode === "model"
                  ? ["models", "figures"]
                  : undefined
          }
        />
      ) : null}
      {results && mode === "design" ? (
        <Frame3dDesignCard results={results} />
      ) : results && mode !== "foundation" ? (
        <Frame3dResultCard results={results} downloads={false} />
      ) : mode !== "model" && !incomplete ? (
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
      setError(null);
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
