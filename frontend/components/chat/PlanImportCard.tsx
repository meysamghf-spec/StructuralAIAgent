import Link from "next/link";

import type { PlanImportResult } from "@/lib/chat-types";

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** DRAFT model imported from a plan drawing: preview, spans, confidence and the review step. */
export function PlanImportCard({ result, projectId }: { result: PlanImportResult; projectId?: string | null }) {
  const low = result.confidence.overall < 0.6;
  return (
    <section className="chat-plan-import" aria-label="Imported model draft" data-testid="plan-import-card">
      <header>
        <strong>Imported model DRAFT</strong> <span>rev {result.revision}</span> · <span>{result.filename}</span>
      </header>
      {result.previewPng ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={result.previewPng} alt="Detected grid axes and columns" style={{ maxWidth: "100%" }} />
      ) : null}
      <ul>
        <li>
          X ({result.labelsX.join(" ")}): {result.spansXM.join(" / ")} m
        </li>
        <li>
          Y ({result.labelsY.join(" ")}): {result.spansYM.join(" / ")} m
        </li>
        <li>
          Columns {result.columns}/{result.intersections} · storeys {result.storeys ?? "—"} · h{" "}
          {result.storeyHeightM ?? "—"} m
        </li>
        <li className={low ? "chat-plan-import-low" : undefined}>
          Confidence: grid {pct(result.confidence.grid)}, spacing {pct(result.confidence.spacing)}, columns{" "}
          {pct(result.confidence.columns)} — overall {pct(result.confidence.overall)}
          {low ? " (check dimensions)" : ""}
        </li>
      </ul>
      {result.edits.length > 0 ? <p>Applied: {result.edits.join("; ")}</p> : null}
      <p>
        Review required before analysis: approve <em>Imported model review</em>
        {projectId ? (
          <>
            {" "}
            on the <Link href={`/workspace/approvals?project=${projectId}${result.approvalId ? `&review=${result.approvalId}` : ""}`}>Approvals page</Link>
          </>
        ) : null}
        , or edit here (e.g. <code>spacing axis 2-3 = 4.5m</code>).
      </p>
    </section>
  );
}
