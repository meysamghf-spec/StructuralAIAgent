import { GRID_LEGEND } from "@/lib/frame3d-viewer";

/** XY (or XZ/YZ) axis indicator + optional north arrow, as an SVG group placed at (x, y) = indicator origin. */
export function OrientationGlyph({ x, y, h = "X", v = "Y", north = true, color = "#e2e8f0" }: { x: number; y: number; h?: string; v?: string; north?: boolean; color?: string }) {
  return (
    <g data-testid="orientation" fontSize={11} fill={color} stroke={color}>
      <line x1={x} y1={y} x2={x + 34} y2={y} strokeWidth={1.5} />
      <path d={`M${x + 40},${y} l-8,-4 l0,8 z`} />
      <text x={x + 44} y={y + 4} stroke="none">{h}</text>
      <line x1={x} y1={y} x2={x} y2={y - 34} strokeWidth={1.5} />
      <path d={`M${x},${y - 40} l-4,8 l8,0 z`} />
      <text x={x - 4} y={y - 44} stroke="none">{v}</text>
      {north ? (
        <g>
          <circle cx={x + 60} cy={y - 26} r={11} fill="none" />
          <path d={`M${x + 60},${y - 37} l-5,17 l5,-4 z`} />
          <path d={`M${x + 60},${y - 37} l5,17 l-5,-4 z`} fill="none" />
          <text x={x + 56} y={y - 41} stroke="none">N</text>
        </g>
      ) : null}
    </g>
  );
}

/** Overlay badge for the 3D viewer's orthographic views. */
export function OrientationBadge({ h, v, north, note }: { h: string; v: string; north: boolean; note?: string }) {
  return (
    <div className="v3d-orient" style={{ position: "absolute", left: 8, bottom: 8, pointerEvents: "none", color: "#e2e8f0", fontSize: 11 }} dir="ltr">
      <svg width={90} height={64} aria-label="axis indicator">
        <OrientationGlyph x={12} y={56} h={h} v={v} north={north} />
      </svg>
      <div>{note ?? GRID_LEGEND}</div>
    </div>
  );
}
