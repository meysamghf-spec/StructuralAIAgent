"use client";

import { ArchitecturalSetViewer } from "@/components/autocad/ArchitecturalSetViewer";
import { listArchSets, type ArchSetMeta } from "@/lib/autocad";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import { useEffect, useState } from "react";

/** Architectural drawing sets (plans, sections, elevations, site, schedule) created from chat. */
export function ArchitecturalSetSection() {
  const [sets, setSets] = useState<ArchSetMeta[] | null>(null);
  const [error, setError] = useState("");
  const [scope, setScope] = useState<"project" | "all">("project");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => {
      setSets(null);
      const pid = getCurrentProjectId();
      if (scope === "project" && !pid) {
        setSets([]); // no active project: show nothing rather than every project's sets
        return;
      }
      listArchSets(scope === "project" ? pid : null)
        .then((s) => { setSets(s); setOpen((o) => o ?? s[0]?.id ?? null); })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    return () => window.removeEventListener(PROJECT_EVENT, sync);
  }, [scope]);

  return (
    <section className="card" data-testid="arch-sets">
      <h3>Architectural sets · نقشه‌های معماری</h3>
      <p className="muted">
        Ask in chat, e.g. «نقشه‌های معماری یک ساختمان ۴ طبقه روی زمین ۱۰×۲۵ بکش» or “architectural drawings for a 4-storey building on a 10×25 plot”.
        Sheets are saved to the project&apos;s Files.
      </p>
      <div className="button-row">
        <button type="button" className={`button${scope === "project" ? "" : " secondary"}`} onClick={() => setScope("project")}>This project</button>
        <button type="button" className={`button${scope === "all" ? "" : " secondary"}`} onClick={() => setScope("all")}>All projects</button>
      </div>
      {error ? <p className="alert error">{error}</p> : null}
      {sets === null && !error ? <p className="muted">Loading…</p> : null}
      {sets && sets.length === 0 ? <p className="muted">No architectural sets yet.</p> : null}
      {sets?.map((s) => (
        <div key={s.id} className="arch-set-item">
          <button type="button" className="arch-set-head" onClick={() => setOpen(open === s.id ? null : s.id)} aria-expanded={open === s.id}>
            <span>{open === s.id ? "▾" : "▸"} {s.title}</span>
            <span className="muted">{s.sheets.length} sheets{s.created_at ? ` · ${new Date(s.created_at).toLocaleString()}` : ""}</span>
          </button>
          {open === s.id ? <ArchitecturalSetViewer set={s} /> : null}
        </div>
      ))}
    </section>
  );
}
