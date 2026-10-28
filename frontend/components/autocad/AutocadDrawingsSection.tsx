"use client";

import { AutocadDrawingCard } from "@/components/autocad/AutocadDrawingCard";
import { listAutocadJobs, type AutocadJobMeta } from "@/lib/autocad";
import { useEffect, useState } from "react";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";

/** AutoCAD drawings produced from chat (PDF/photo → DXF, prompt → plan), shown on the CAD page. */
export function AutocadDrawingsSection() {
  const [jobs, setJobs] = useState<AutocadJobMeta[] | null>(null);
  const [error, setError] = useState("");

  const [scope, setScope] = useState<"project" | "all">("project");

  useEffect(() => {
    const sync = () => {
      const pid = getCurrentProjectId();
      setJobs(null);
      if (scope === "project" && !pid) {
        setJobs([]); // no active project: show nothing rather than every project's drawings
        return;
      }
      listAutocadJobs(scope === "project" ? pid : null)
        .then((js) => setJobs(js.filter((j) => (j.kind as string) !== "structural")))
        .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    return () => window.removeEventListener(PROJECT_EVENT, sync);
  }, [scope]);

  return (
    <section className="card" data-testid="autocad-drawings">
      <h3>AutoCAD drawings</h3>
      <p className="muted">Created in chat. DXF files are also saved to the project&apos;s Files.</p>
      <div className="button-row">
        <button type="button" className={`button${scope === "project" ? "" : " secondary"}`} onClick={() => setScope("project")}>
          This project
        </button>
        <button type="button" className={`button${scope === "all" ? "" : " secondary"}`} onClick={() => setScope("all")}>
          All projects
        </button>
      </div>
      {error ? <p className="alert error">{error}</p> : null}
      {jobs === null && !error ? <p className="muted">Loading…</p> : null}
      {jobs && jobs.length === 0 ? (
        <p className="muted">No AutoCAD drawings yet — attach a PDF or photo in chat, or ask it to draw a plan.</p>
      ) : null}
      <div className="autocad-grid">
        {jobs?.map((j) => (
          <AutocadDrawingCard
            key={j.id}
            jobId={j.id}
            kind={j.kind}
            title={`${j.kind === "vectorize" ? "Converted" : "Drawn"}: ${j.source || j.id.slice(0, 8)}`}
            filename={`autocad-${j.kind}-${j.id.slice(0, 8)}.dxf`}
            layers={j.layers}
            review={j.review}
            savedToProject={!!j.project_file_id}
          />
        ))}
      </div>
    </section>
  );
}
