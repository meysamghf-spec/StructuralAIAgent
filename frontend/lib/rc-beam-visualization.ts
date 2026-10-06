/** Derive RC beam Demo diagrams from existing engineering_results. */

import type { DemoEngineeringResults } from "./chat-types";

export const DEMO_VISUAL_DISCLAIMER =
  "Demonstration calculation — not a final structural design.";

export type RcBeamDemoModel = {
  spanM: number;
  uniformLoadKnM: number;
  widthMm: number | null;
  heightMm: number | null;
  effectiveDepthMm: number | null;
  fcMpa: number | null;
  fyMpa: number | null;
  maxMomentKnM: number;
  maxShearKn: number;
};

export type RcBeamStation = {
  xM: number;
  shearKn: number;
  momentKnM: number;
};

export type PlotBox = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type VisualizationCopy = {
  title: string;
  spanLabel: string;
  loadLabel: string;
  mmaxLabel: string;
  vmaxLabel: string;
  sectionLabel: string | null;
  depthLabel: string | null;
  fcLabel: string | null;
  fyLabel: string | null;
  disclaimer: string;
};

function parseFinite(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value.replace(/,/g, "").trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function fieldValue(results: DemoEngineeringResults, labels: string[]): number | null {
  const wanted = labels.map((label) => label.toLowerCase());
  for (const field of results.fields) {
    if (wanted.includes(field.label.toLowerCase())) {
      return parseFinite(field.value);
    }
  }
  return null;
}

function parseSection(results: DemoEngineeringResults): { widthMm: number; heightMm: number } | null {
  const field = results.fields.find((item) => item.label.toLowerCase() === "section");
  if (!field) {
    return null;
  }
  const match = field.value.match(/(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)/i);
  if (!match) {
    return null;
  }
  return { widthMm: Number(match[1]), heightMm: Number(match[2]) };
}

export function parseRcBeamDemoModel(results: DemoEngineeringResults): RcBeamDemoModel | null {
  const section = parseSection(results);
  const spanM = results.inputs?.spanM ?? fieldValue(results, ["span"]);
  const uniformLoadKnM =
    results.inputs?.uniformLoadKnM ?? fieldValue(results, ["uniform load", "udl"]);
  const maxMomentKnM =
    results.numericResults?.maxMomentKnM ?? fieldValue(results, ["maximum moment", "mmax"]);
  const maxShearKn =
    results.numericResults?.maxShearKn ?? fieldValue(results, ["maximum shear", "vmax"]);

  if (
    spanM === null ||
    spanM <= 0 ||
    uniformLoadKnM === null ||
    maxMomentKnM === null ||
    maxShearKn === null
  ) {
    return null;
  }

  return {
    spanM,
    uniformLoadKnM,
    widthMm: results.inputs?.widthMm ?? section?.widthMm ?? null,
    heightMm: results.inputs?.heightMm ?? section?.heightMm ?? null,
    effectiveDepthMm: results.inputs?.effectiveDepthMm ?? fieldValue(results, ["effective depth"]),
    fcMpa: results.inputs?.fcMpa ?? fieldValue(results, ["fc"]),
    fyMpa: results.inputs?.fyMpa ?? fieldValue(results, ["fy"]),
    maxMomentKnM,
    maxShearKn,
  };
}

export function reactionKn(model: RcBeamDemoModel): number {
  return (model.uniformLoadKnM * model.spanM) / 2;
}

export function shearAt(model: RcBeamDemoModel, xM: number): number {
  return reactionKn(model) - model.uniformLoadKnM * xM;
}

export function momentAt(model: RcBeamDemoModel, xM: number): number {
  const reaction = reactionKn(model);
  return reaction * xM - (model.uniformLoadKnM * xM * xM) / 2;
}

export function sampleRcBeamStations(model: RcBeamDemoModel, count = 25): RcBeamStation[] {
  const samples = Math.max(3, count);
  const stations: RcBeamStation[] = [];
  for (let index = 0; index < samples; index += 1) {
    const xM = (model.spanM * index) / (samples - 1);
    stations.push({
      xM,
      shearKn: shearAt(model, xM),
      momentKnM: momentAt(model, xM),
    });
  }
  return stations;
}

export function formatEngineeringNumber(value: number, digits = 2): string {
  return value.toFixed(digits);
}

export function visualizationCopy(model: RcBeamDemoModel): VisualizationCopy {
  return {
    title: "RC beam analysis",
    spanLabel: `${formatEngineeringNumber(model.spanM)} m`,
    loadLabel: `${formatEngineeringNumber(model.uniformLoadKnM)} kN/m`,
    mmaxLabel: `${formatEngineeringNumber(model.maxMomentKnM)} kN·m`,
    vmaxLabel: `${formatEngineeringNumber(model.maxShearKn)} kN`,
    sectionLabel:
      model.widthMm !== null && model.heightMm !== null
        ? `${formatEngineeringNumber(model.widthMm, 0)} × ${formatEngineeringNumber(model.heightMm, 0)} mm`
        : null,
    depthLabel:
      model.effectiveDepthMm !== null
        ? `${formatEngineeringNumber(model.effectiveDepthMm, 0)} mm`
        : null,
    fcLabel: model.fcMpa !== null ? `${formatEngineeringNumber(model.fcMpa, 0)} MPa` : null,
    fyLabel: model.fyMpa !== null ? `${formatEngineeringNumber(model.fyMpa, 0)} MPa` : null,
    disclaimer: DEMO_VISUAL_DISCLAIMER,
  };
}

export function spanPositionFromClientX(
  clientX: number,
  svgLeft: number,
  svgWidth: number,
  plot: PlotBox,
  viewBoxWidth: number,
  spanM: number,
): number {
  const svgX = ((clientX - svgLeft) / Math.max(svgWidth, 1)) * viewBoxWidth;
  const clamped = Math.min(plot.left + plot.width, Math.max(plot.left, svgX));
  return ((clamped - plot.left) / plot.width) * spanM;
}

export function polylineFromStations(
  stations: RcBeamStation[],
  plot: PlotBox,
  spanM: number,
  valueOf: (station: RcBeamStation) => number,
  valueScale: number,
  baselineY: number,
  invert = false,
): string {
  return stations
    .map((station) => {
      const x = plot.left + (station.xM / spanM) * plot.width;
      const offset = (valueOf(station) / valueScale) * (plot.height / 2);
      const y = invert ? baselineY + offset : baselineY - offset;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function closedAreaFromStations(
  stations: RcBeamStation[],
  plot: PlotBox,
  spanM: number,
  valueOf: (station: RcBeamStation) => number,
  valueScale: number,
  baselineY: number,
  invert = false,
): string {
  const line = polylineFromStations(stations, plot, spanM, valueOf, valueScale, baselineY, invert);
  const firstX = plot.left.toFixed(2);
  const lastX = (plot.left + plot.width).toFixed(2);
  return `${firstX},${baselineY.toFixed(2)} ${line} ${lastX},${baselineY.toFixed(2)}`;
}

export function hoverReadout(model: RcBeamDemoModel, xM: number): {
  xM: number;
  momentKnM: number;
  shearKn: number;
} {
  const clamped = Math.min(model.spanM, Math.max(0, xM));
  return {
    xM: clamped,
    momentKnM: momentAt(model, clamped),
    shearKn: shearAt(model, clamped),
  };
}
