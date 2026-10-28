"use client";

import { StructuralSetView } from "@/components/autocad/StructuralSetView";
import { generateStructuralSet, listStructuralSets, type StructuralSet } from "@/lib/structural-set";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import { useCallback, useEffect, useState } from "react";

/** CAD page: structural drawing sets (S-101…S-501) built from the project's 3D frame analysis + Mabhas 9 design. */
export function StructuralSetSection() {
  const [sets, setSets] = useState<StructuralSet[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    const p = getCurrentProjectId();
    setPid(p);
    setSets(null);
    if (!p) {
      setSets([]); // no active project: show nothing rather than every project's sets
      return;
    }
    listStructuralSets(p)
      .then(setSets)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    load();
    window.addEventListener(PROJECT_EVENT, load);
    return () => window.removeEventListener(PROJECT_EVENT, load);
  }, [load]);

  async function generate() {
    setBusy(true);
    setError("");
    try {
      const s = await generateStructuralSet(pid);
      setSets((prev) => [s, ...(prev ?? [])]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" data-testid="structural-sets">
      <h3>Structural drawings · نقشه‌های اجرایی سازه</h3>
      <p className="muted">
        Column &amp; beam layouts with schedules, typical beam rebar elevations, column sections, foundation and frame
        elevations — one DXF per sheet plus a combined PDF, from the latest 3D frame analysis (Mabhas 9). In chat you can
        also ask «نقشه‌های اجرایی سازه را بده».
      </p>
      <div className="button-row">
        <button type="button" className="button" disabled={busy || !pid} onClick={() => void generate()}>
          {busy ? "Generating sheets…" : "Generate structural drawings"}
        </button>
      </div>
      {!pid ? <p className="muted">Select a project first.</p> : null}
      {error ? <p className="alert error">{error}</p> : null}
      {sets === null && !error ? <p className="muted">Loading…</p> : null}
      {sets && sets.length === 0 ? <p className="muted">No structural drawing set yet for this project.</p> : null}
      {sets?.slice(0, 3).map((s, i) => <StructuralSetView key={s.id} set={s} compact={i > 0} />)}
    </section>
  );
}
