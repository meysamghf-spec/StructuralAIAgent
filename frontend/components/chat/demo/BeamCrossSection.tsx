import type { RcBeamDemoModel, VisualizationCopy } from "@/lib/rc-beam-visualization";

type BeamCrossSectionProps = {
  model: RcBeamDemoModel;
  copy: VisualizationCopy;
};

export function BeamCrossSection({ model, copy }: BeamCrossSectionProps) {
  if (model.widthMm === null || model.heightMm === null) {
    return (
      <p className="muted">Cross-section geometry is not available on this result.</p>
    );
  }

  const width = 160;
  const height = (model.heightMm / model.widthMm) * width;
  const depthRatio =
    model.effectiveDepthMm !== null ? Math.min(0.96, model.effectiveDepthMm / model.heightMm) : 0.9;
  const dY = 28 + height * depthRatio;
  const barYTop = 28 + 18;
  const barYBot = 28 + height - 18;

  return (
    <figure className="rc-diagram">
      <figcaption className="engineering-result-label">Beam cross-section</figcaption>
      <svg
        className="rc-svg rc-svg-section"
        viewBox={`0 0 280 ${height + 86}`}
        role="img"
        aria-label={`Rectangular RC section ${copy.sectionLabel ?? ""}, effective depth ${copy.depthLabel ?? "not specified"}`}
      >
        <text x="140" y="18" textAnchor="middle" className="rc-svg-label">
          {copy.sectionLabel ? `b = ${model.widthMm.toFixed(0)} mm` : ""}
        </text>
        <rect
          x={140 - width / 2}
          y="28"
          width={width}
          height={height}
          fill="rgba(148, 163, 184, 0.12)"
          stroke="#cbd5e1"
          strokeWidth="2"
        />
        {[140 - 36, 140 + 36].map((x) => (
          <circle key={`t-${x}`} cx={x} cy={barYTop} r="6" fill="#e2e8f0" />
        ))}
        {[140 - 36, 140 + 36].map((x) => (
          <circle key={`b-${x}`} cx={x} cy={barYBot} r="6" fill="#e2e8f0" />
        ))}
        <line x1={140 + width / 2 + 10} y1="28" x2={140 + width / 2 + 10} y2={28 + height} stroke="#94a3b8" />
        <text x={140 + width / 2 + 18} y={28 + height / 2} className="rc-svg-label">
          h = {model.heightMm.toFixed(0)} mm
        </text>
        {model.effectiveDepthMm !== null ? (
          <>
            <line x1={140 - width / 2 - 10} y1="28" x2={140 - width / 2 - 10} y2={dY} stroke="#38bdf8" />
            <line x1={140 - width / 2 - 16} y1={dY} x2={140 + 20} y2={dY} stroke="#38bdf8" strokeDasharray="3 3" />
            <text x={36} y={(28 + dY) / 2} className="rc-svg-label">
              d = {model.effectiveDepthMm.toFixed(0)} mm
            </text>
          </>
        ) : null}
        <text x="140" y={height + 58} textAnchor="middle" className="rc-svg-label">
          Bars are a conceptual Demo representation
        </text>
      </svg>
    </figure>
  );
}
