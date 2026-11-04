import { DESIGN_LEGEND } from "@/lib/design-dc";

/** Bilingual (Persian / English) legend shown under the Mabhas 9 design tables. */
export function DesignLegend({ className }: { className?: string }) {
  return (
    <details className={`design-legend ${className ?? ""}`} data-testid="design-legend" open>
      <summary>Legend · راهنما</summary>
      <ul>
        {DESIGN_LEGEND.map((l) => (
          <li key={l.en}>
            <span dir="ltr" lang="en">{l.en}</span>
            <span dir="rtl" lang="fa">{l.fa}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
