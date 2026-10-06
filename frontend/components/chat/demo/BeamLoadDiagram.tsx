"use client";

import {
  type PlotBox,
  type RcBeamDemoModel,
  type VisualizationCopy,
  spanPositionFromClientX,
} from "@/lib/rc-beam-visualization";
import { useId, type KeyboardEvent, type PointerEvent } from "react";

const VIEW_W = 640;
const VIEW_H = 220;
const PLOT: PlotBox = { left: 80, top: 46, width: 480, height: 70 };

type BeamLoadDiagramProps = {
  model: RcBeamDemoModel;
  copy: VisualizationCopy;
  hoverXM: number | null;
  onHover: (xM: number | null) => void;
};

export function BeamLoadDiagram({ model, copy, hoverXM, onHover }: BeamLoadDiagramProps) {
  const markerId = useId();
  const x0 = PLOT.left;
  const x1 = PLOT.left + PLOT.width;
  const beamY = 118;
  const arrowCount = 9;
  const arrows = Array.from({ length: arrowCount }, (_, index) => x0 + (PLOT.width * index) / (arrowCount - 1));
  const hoverX =
    hoverXM === null ? null : x0 + (hoverXM / model.spanM) * PLOT.width;

  function updateFromClientX(clientX: number, currentTarget: Element) {
    const rect = currentTarget.getBoundingClientRect();
    onHover(spanPositionFromClientX(clientX, rect.left, rect.width, PLOT, VIEW_W, model.spanM));
  }

  function handlePointer(event: PointerEvent<SVGSVGElement>) {
    updateFromClientX(event.clientX, event.currentTarget);
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
      <figcaption className="engineering-result-label">Beam / load diagram</figcaption>
      <svg
        className="rc-svg"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="img"
        tabIndex={0}
        aria-label={`Simply supported RC beam, span ${copy.spanLabel}, uniform load ${copy.loadLabel}`}
        onPointerMove={handlePointer}
        onPointerLeave={() => onHover(null)}
        onKeyDown={handleKey}
      >
        <defs>
          <marker
            id={`${markerId}-arrow`}
            markerWidth="8"
            markerHeight="8"
            refX="4"
            refY="4"
            orient="auto"
          >
            <path d="M1 1 L7 4 L1 7 Z" fill="#f8b860" />
          </marker>
        </defs>
        <text x={VIEW_W / 2} y="22" textAnchor="middle" className="rc-svg-title">
          RC Beam Demo
        </text>
        <text x={VIEW_W / 2} y="44" textAnchor="middle" className="rc-svg-label">
          {copy.loadLabel}
        </text>
        {arrows.map((x) => (
          <line
            key={x}
            className="rc-load-arrow"
            x1={x}
            y1="56"
            x2={x}
            y2="100"
            stroke="#f8b860"
            strokeWidth="1.4"
            markerEnd={`url(#${markerId}-arrow)`}
          />
        ))}
        <line x1={x0} y1="56" x2={x1} y2="56" stroke="#f8b860" strokeWidth="1" opacity="0.55" />
        <rect x={x0} y={beamY - 8} width={PLOT.width} height="16" rx="2" fill="#cbd5e1" />
        <polygon points={`${x0},${beamY + 10} ${x0 - 12},${beamY + 34} ${x0 + 12},${beamY + 34}`} fill="#94a3b8" />
        <circle cx={x1} cy={beamY + 28} r="7" fill="none" stroke="#94a3b8" strokeWidth="2" />
        <polygon points={`${x1},${beamY + 10} ${x1 - 10},${beamY + 22} ${x1 + 10},${beamY + 22}`} fill="#94a3b8" />
        <text x={x0} y={beamY + 52} textAnchor="middle" className="rc-svg-label">
          Pin
        </text>
        <text x={x1} y={beamY + 52} textAnchor="middle" className="rc-svg-label">
          Roller
        </text>
        <line x1={x0} y1="186" x2={x1} y2="186" stroke="#94a3b8" strokeWidth="1" />
        <line x1={x0} y1="180" x2={x0} y2="192" stroke="#94a3b8" strokeWidth="1" />
        <line x1={x1} y1="180" x2={x1} y2="192" stroke="#94a3b8" strokeWidth="1" />
        <text x={VIEW_W / 2} y="208" textAnchor="middle" className="rc-svg-label">
          {copy.spanLabel}
        </text>
        {hoverX !== null ? (
          <line
            x1={hoverX}
            y1="52"
            x2={hoverX}
            y2="170"
            stroke="#38bdf8"
            strokeDasharray="3 3"
            strokeWidth="1"
          />
        ) : null}
      </svg>
    </figure>
  );
}
