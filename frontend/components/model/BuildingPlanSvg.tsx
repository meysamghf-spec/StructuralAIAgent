"use client";

import { polygonPoints, spaceFill, type BuildingFloor, type BuildingView } from "@/lib/building";

type BuildingPlanSvgProps = {
  view: BuildingView;
  floor: BuildingFloor | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export function BuildingPlanSvg({ view, floor, selectedId, onSelect }: BuildingPlanSvgProps) {
  const site = view.site;
  const width = site?.frontage_m || 12;
  const height = site?.depth_m || 22;
  const pad = 1.2;

  return (
    <svg
      className="building-plan-svg"
      viewBox={`${-pad} ${-pad} ${width + pad * 2} ${height + pad * 2}`}
      role="img"
      aria-label="Generated floor plan"
    >
      <g transform={`scale(1,-1) translate(0, ${-height})`}>
        {site ? (
          <polygon className="building-plan-plot" points={polygonPoints(site.boundary)} />
        ) : null}
        {floor
          ? floor.spaces.map((space) => (
              <polygon
                key={space.id}
                className={selectedId === space.id ? "building-plan-space is-selected" : "building-plan-space"}
                points={polygonPoints(space.boundary)}
                fill={spaceFill(space.usage)}
                onClick={() => onSelect(space.id)}
              />
            ))
          : null}
        {floor
          ? floor.parking_spaces.map((slot) => (
              <polygon
                key={slot.id}
                className="building-plan-parking"
                points={polygonPoints(slot.boundary)}
                onClick={() => onSelect(slot.id)}
              />
            ))
          : null}
        {view.grid.x_ordinates.map((x, index) => (
          <line
            key={`gx-${index}`}
            className="building-plan-grid"
            x1={x}
            y1={0}
            x2={x}
            y2={height}
          />
        ))}
        {view.grid.y_ordinates.map((y, index) => (
          <line
            key={`gy-${index}`}
            className="building-plan-grid"
            x1={0}
            y1={y}
            x2={width}
            y2={y}
          />
        ))}
        {view.beams.map((beam) =>
          beam.start && beam.end ? (
            <line
              key={beam.id}
              className={selectedId === beam.id ? "building-plan-beam is-selected" : "building-plan-beam"}
              x1={beam.start.x}
              y1={beam.start.y}
              x2={beam.end.x}
              y2={beam.end.y}
              onClick={() => onSelect(beam.id)}
            />
          ) : null,
        )}
        {view.columns.map((column) =>
          column.x == null || column.y == null ? null : (
            <rect
              key={column.id}
              className={selectedId === column.id ? "building-plan-column is-selected" : "building-plan-column"}
              x={column.x - 0.15}
              y={column.y - 0.15}
              width={0.3}
              height={0.3}
              onClick={() => onSelect(column.id)}
            />
          ),
        )}
      </g>
    </svg>
  );
}
