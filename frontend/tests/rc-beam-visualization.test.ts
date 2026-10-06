import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { DemoEngineeringResults } from "../lib/chat-types";
import {
  DEMO_VISUAL_DISCLAIMER,
  hoverReadout,
  momentAt,
  parseRcBeamDemoModel,
  reactionKn,
  sampleRcBeamStations,
  shearAt,
  visualizationCopy,
} from "../lib/rc-beam-visualization";

function demoPayload(overrides: Partial<DemoEngineeringResults> = {}): DemoEngineeringResults {
  return {
    kind: "demo_rc_beam",
    status: "completed",
    demo: true,
    disclaimer: "Demo calculation. Final engineering decisions require verification by a qualified engineer.",
    code: "Demo / configured project code profile",
    fields: [],
    assumptions: [],
    warnings: [],
    inputs: {
      spanM: 6,
      uniformLoadKnM: 20,
      widthMm: 300,
      heightMm: 500,
      effectiveDepthMm: 450,
      fcMpa: 25,
      fyMpa: 400,
    },
    numericResults: {
      maxMomentKnM: 90,
      maxShearKn: 60,
    },
    ...overrides,
  };
}

describe("RC beam visualization math", () => {
  const model = parseRcBeamDemoModel(demoPayload());

  it("parses span, load, section, and materials from the payload", () => {
    expect(model).not.toBeNull();
    expect(model?.spanM).toBe(6);
    expect(model?.uniformLoadKnM).toBe(20);
    expect(model?.widthMm).toBe(300);
    expect(model?.heightMm).toBe(500);
    expect(model?.effectiveDepthMm).toBe(450);
    expect(model?.fcMpa).toBe(25);
    expect(model?.fyMpa).toBe(400);
    expect(model?.maxMomentKnM).toBe(90);
    expect(model?.maxShearKn).toBe(60);
  });

  it("computes reactions and moment/shear stations from payload inputs", () => {
    if (!model) {
      throw new Error("expected parsed model");
    }
    expect(reactionKn(model)).toBeCloseTo(60);
    expect(momentAt(model, 0)).toBeCloseTo(0);
    expect(momentAt(model, 3)).toBeCloseTo(90);
    expect(momentAt(model, 6)).toBeCloseTo(0);
    expect(shearAt(model, 0)).toBeCloseTo(60);
    expect(shearAt(model, 3)).toBeCloseTo(0);
    expect(shearAt(model, 6)).toBeCloseTo(-60);
  });

  it("samples a parabolic moment and linear shear diagram", () => {
    if (!model) {
      throw new Error("expected parsed model");
    }
    const stations = sampleRcBeamStations(model, 25);
    expect(stations[0]?.momentKnM).toBeCloseTo(0);
    expect(stations[12]?.momentKnM).toBeCloseTo(90);
    expect(stations[24]?.momentKnM).toBeCloseTo(0);
    expect(stations[0]?.shearKn).toBeCloseTo(60);
    expect(stations[12]?.shearKn).toBeCloseTo(0);
    expect(stations[24]?.shearKn).toBeCloseTo(-60);
  });

  it("builds display copy from payload values rather than hardcoded Demo numbers", () => {
    if (!model) {
      throw new Error("expected parsed model");
    }
    const copy = visualizationCopy(model);
    expect(copy.spanLabel).toBe("6.00 m");
    expect(copy.loadLabel).toBe("20.00 kN/m");
    expect(copy.mmaxLabel).toBe("90.00 kN·m");
    expect(copy.vmaxLabel).toBe("60.00 kN");
    expect(copy.sectionLabel).toBe("300 × 500 mm");
    expect(copy.depthLabel).toBe("450 mm");
    expect(copy.fcLabel).toBe("25 MPa");
    expect(copy.fyLabel).toBe("400 MPa");
    expect(copy.disclaimer).toBe(DEMO_VISUAL_DISCLAIMER);
  });

  it("returns a synchronized hover readout", () => {
    if (!model) {
      throw new Error("expected parsed model");
    }
    const readout = hoverReadout(model, 3);
    expect(readout.xM).toBeCloseTo(3);
    expect(readout.momentKnM).toBeCloseTo(90);
    expect(readout.shearKn).toBeCloseTo(0);
  });

  it("falls back to field labels when structured inputs are missing", () => {
    const parsed = parseRcBeamDemoModel(
      demoPayload({
        inputs: null,
        numericResults: null,
        fields: [
          { label: "Span", value: "6.00", unit: "m" },
          { label: "Uniform Load", value: "20.00", unit: "kN/m" },
          { label: "Section", value: "300 × 500", unit: "mm" },
          { label: "Effective depth", value: "450", unit: "mm" },
          { label: "fc", value: "25", unit: "MPa" },
          { label: "fy", value: "400", unit: "MPa" },
          { label: "Maximum Moment", value: "90.00", unit: "kN·m" },
          { label: "Maximum Shear", value: "60.00", unit: "kN" },
        ],
      }),
    );
    expect(parsed).not.toBeNull();
    expect(parsed?.spanM).toBe(6);
    expect(parsed?.maxMomentKnM).toBe(90);
    expect(visualizationCopy(parsed!).sectionLabel).toBe("300 × 500 mm");
  });

  it("does not invent a model when required values are missing", () => {
    expect(
      parseRcBeamDemoModel(
        demoPayload({
          inputs: null,
          numericResults: null,
          fields: [{ label: "Maximum Moment", value: "90.00", unit: "kN·m" }],
        }),
      ),
    ).toBeNull();
  });
});

describe("chat graphical Demo integration", () => {
  it("renders RCDemoVisualization from EngineeringResultCard", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/chat/EngineeringResultCard.tsx"),
      "utf8",
    );
    expect(source).toContain("RCDemoVisualization");
    expect(source).toContain("parseRcBeamDemoModel");
    expect(source).toContain("Graphical analysis becomes available");
  });

  it("composes existing SVG engineering diagrams in the orchestrator", async () => {
    const orchestrator = await import("../components/chat/demo/RCDemoVisualization");
    expect(orchestrator.RCDemoVisualization).toBeTypeOf("function");
    const source = readFileSync(
      resolve(__dirname, "../components/chat/demo/RCDemoVisualization.tsx"),
      "utf8",
    );
    expect(source).toContain("BeamLoadDiagram");
    expect(source).toContain("MomentDiagram");
    expect(source).toContain("ShearDiagram");
    expect(source).toContain("BeamCrossSection");
    expect(source).toContain("EngineeringParameters");
    expect(source).toContain("EngineeringResultsSummary");
    expect(source).toContain("AnalysisWorkflow");
    expect(source).toContain("hoverReadout");
  });
});
