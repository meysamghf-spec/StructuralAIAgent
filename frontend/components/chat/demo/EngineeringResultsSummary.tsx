import type { VisualizationCopy } from "@/lib/rc-beam-visualization";

type EngineeringResultsSummaryProps = {
  copy: VisualizationCopy;
};

export function EngineeringResultsSummary({ copy }: EngineeringResultsSummaryProps) {
  return (
    <div className="rc-results-summary">
      <article className="rc-result-metric">
        <p className="engineering-result-label">Mmax</p>
        <p className="rc-result-value">{copy.mmaxLabel}</p>
      </article>
      <article className="rc-result-metric">
        <p className="engineering-result-label">Vmax</p>
        <p className="rc-result-value">{copy.vmaxLabel}</p>
      </article>
    </div>
  );
}
