"use client";

import { AutocadDrawingCard } from "@/components/autocad/AutocadDrawingCard";
import { listAutocadJobs, type AutocadJobMeta } from "@/lib/autocad";
import { useEffect, useState } from "react";

/** AutoCAD drawings produced from chat (PDF/photo → DXF, prompt → plan), shown on the CAD page. */
export function AutocadDrawingsSection() {
  const [jobs, setJobs] = useState<AutocadJobMeta[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listAutocadJobs().then(setJobs).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <section className="card" data-testid="autocad-drawings">
      <h3>AutoCAD drawings</h3>
      <p className="muted">Created in chat. DXF files are also saved to the project&apos;s Files.</p>
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
