"use client";

import {
  closedAreaFromStations,
  polylineFromStations,
  sampleRcBeamStations,
  spanPositionFromClientX,
  type PlotBox,
  type RcBeamDemoModel,
  type VisualizationCopy,
} from "@/lib/rc-beam-visualization";
import { useMemo, type KeyboardEvent, type PointerEvent } from "react";

const VIEW_W = 420;
const VIEW_H = 210;
const PLOT: PlotBox = { left: 56, top: 28, width: 330, height: 130 };

type MomentDiagramProps = {
  model: RcBeamDemoModel;
  copy: VisualizationCopy;
  hoverXM: number | null;
  onHover: (xM: number | null) => void;
};

export function MomentDiagram({ model, copy, hoverXM, onHover }: MomentDiagramProps) {
  const stations = useMemo(() => sampleRcBeamStations(model, 33), [model]);
  const baselineY = PLOT.top + 18;
  const valueScale = Math.max(model.maxMomentKnM, 1);
  const area = closedAreaFromStations(
    stations,
    PLOT,
    model.spanM,
    (station) => station.momentKnM,
    valueScale,
    baselineY,
    true,
  );
  const line = polylineFromStations(
    stations,
    PLOT,
    model.spanM,
    (station) => station.momentKnM,
    valueScale,
    baselineY,
    true,
  );
  const midX = PLOT.left + PLOT.width / 2;
  const hoverX = hoverXM === null ? null : PLOT.left + (hoverXM / model.spanM) * PLOT.width;

  function handlePointer(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    onHover(spanPositionFromClientX(event.clientX, rect.left, rect.width, PLOT, VIEW_W, model.spanM));
  }

  function handleKey(event: KeyboardEvent<SVGSVGElement>) {
    const step = model.spanM / 20;
    const current = hoverXM ?? model.spanM / 2;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      onHover(Math.min(model.spanM, current + step));
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      onHover(Math.max(0, current - step));
    }
    if (event.key === "Escape") {
      onHover(null);
    }
  }

  return (
    <figure className="rc-diagram">
      <div className="rc-diagram-heading">
        <figcaption className="engineering-result-label">Bending moment diagram</figcaption>
        <p className="rc-diagram-badge">Mmax {copy.mmaxLabel}</p>
      </div>
      <svg
        className="rc-svg"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="img"
        tabIndex={0}
        aria-label={`Bending moment diagram, zero at supports, maximum ${copy.mmaxLabel} at midspan`}
        onPointerMove={handlePointer}
        onPointerLeave={() => onHover(null)}
        onKeyDown={handleKey}
      >
        <line
          x1={PLOT.left}
          y1={baselineY}
          x2={PLOT.left + PLOT.width}
          y2={baselineY}
          stroke="#64748b"
          strokeWidth="1"
        />
        <line x1={PLOT.left} y1={PLOT.top} x2={PLOT.left} y2={PLOT.top + PLOT.height} stroke="#64748b" strokeWidth="1" />
        <polygon className="rc-diagram-fill" points={area} fill="rgba(56, 189, 248, 0.22)" />
        <polyline className="rc-diagram-curve" points={line} fill="none" stroke="#38bdf8" strokeWidth="2" />
        <text x={PLOT.left - 8} y={baselineY + 4} textAnchor="end" className="rc-svg-label">
          0
        </text>
        <text x={PLOT.left + PLOT.width + 8} y={baselineY + 4} className="rc-svg-label">
          0
        </text>
        <text x={midX} y={baselineY + PLOT.height / 2 + 18} textAnchor="middle" className="rc-svg-label">
          {copy.mmaxLabel}
        </text>
        <text x={midX} y={PLOT.top + PLOT.height + 18} textAnchor="middle" className="rc-svg-label">
          midspan
        </text>
        {hoverX !== null ? (
          <line x1={hoverX} y1={PLOT.top} x2={hoverX} y2={PLOT.top + PLOT.height} stroke="#e2e8f0" strokeDasharray="3 3" />
        ) : null}
      </svg>
    </figure>
  );
}
