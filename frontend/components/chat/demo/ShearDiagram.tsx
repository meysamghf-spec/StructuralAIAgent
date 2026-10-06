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
const PLOT: PlotBox = { left: 62, top: 28, width: 320, height: 130 };

type ShearDiagramProps = {
  model: RcBeamDemoModel;
  copy: VisualizationCopy;
  hoverXM: number | null;
  onHover: (xM: number | null) => void;
};

export function ShearDiagram({ model, copy, hoverXM, onHover }: ShearDiagramProps) {
  const stations = useMemo(() => sampleRcBeamStations(model, 3), [model]);
  const baselineY = PLOT.top + PLOT.height / 2;
  const valueScale = Math.max(model.maxShearKn, 1);
  const area = closedAreaFromStations(
    stations,
    PLOT,
    model.spanM,
    (station) => station.shearKn,
    valueScale,
    baselineY,
  );
  const line = polylineFromStations(
    stations,
    PLOT,
    model.spanM,
    (station) => station.shearKn,
    valueScale,
    baselineY,
  );
  const hoverX = hoverXM === null ? null : PLOT.left + (hoverXM / model.spanM) * PLOT.width;

  function handlePointer(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    onHover(spanPositionFromClientX(event.clientX, rect.left, rect.width, PLOT, VIEW_W, model.spanM));
  }

  function handleKey(event: KeyboardEvent<SVGSVGElement>) {
    const step = model.spanM / 20;
    const current = hoverXM ?? 0;
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
        <figcaption className="engineering-result-label">Shear force diagram</figcaption>
        <p className="rc-diagram-badge">Vmax {copy.vmaxLabel}</p>
      </div>
      <svg
        className="rc-svg"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="img"
        tabIndex={0}
        aria-label={`Shear force diagram, plus ${copy.vmaxLabel} at the left support, zero at midspan, minus ${copy.vmaxLabel} at the right support`}
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
        <polygon className="rc-diagram-fill" points={area} fill="rgba(45, 212, 191, 0.18)" />
        <polyline className="rc-diagram-curve" points={line} fill="none" stroke="#2dd4bf" strokeWidth="2" />
        <text x={PLOT.left - 8} y={PLOT.top + 10} textAnchor="end" className="rc-svg-label">
          +{copy.vmaxLabel}
        </text>
        <text x={PLOT.left - 8} y={PLOT.top + PLOT.height} textAnchor="end" className="rc-svg-label">
          −{copy.vmaxLabel}
        </text>
        <text x={PLOT.left + PLOT.width / 2} y={baselineY - 8} textAnchor="middle" className="rc-svg-label">
          0
        </text>
        {hoverX !== null ? (
          <line x1={hoverX} y1={PLOT.top} x2={hoverX} y2={PLOT.top + PLOT.height} stroke="#e2e8f0" strokeDasharray="3 3" />
        ) : null}
      </svg>
    </figure>
  );
}
