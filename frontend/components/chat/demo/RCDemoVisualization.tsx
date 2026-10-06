"use client";

import { AnalysisWorkflow } from "./AnalysisWorkflow";
import { BeamCrossSection } from "./BeamCrossSection";
import { BeamLoadDiagram } from "./BeamLoadDiagram";
import { EngineeringParameters } from "./EngineeringParameters";
import { EngineeringResultsSummary } from "./EngineeringResultsSummary";
import { MomentDiagram } from "./MomentDiagram";
import { ShearDiagram } from "./ShearDiagram";
import {
  formatEngineeringNumber,
  hoverReadout,
  reactionKn,
  visualizationCopy,
  type RcBeamDemoModel,
} from "@/lib/rc-beam-visualization";
import type { DemoEngineeringResults } from "@/lib/chat-types";
import { useMemo, useState } from "react";

type RCDemoVisualizationProps = {
  results: DemoEngineeringResults;
  model: RcBeamDemoModel;
};

export function RCDemoVisualization({ results, model }: RCDemoVisualizationProps) {
  const copy = useMemo(() => visualizationCopy(model), [model]);
  const [hoverXM, setHoverXM] = useState<number | null>(null);
  const readout = hoverXM === null ? null : hoverReadout(model, hoverXM);
  const reaction = reactionKn(model);

  return (
    <div className="rc-demo">
      <header className="rc-demo-header">
        <div>
          <p className="eyebrow">RC beam analysis</p>
          <h3>{copy.title}</h3>
        </div>
        <div className="engineering-result-badges">
          {results.demo ? <span className="chat-progress-badge warning">Demo calculation</span> : null}
          <span className="chat-progress-badge">{results.status.replace(/_/g, " ")}</span>
        </div>
      </header>

      <AnalysisWorkflow />

      <BeamLoadDiagram model={model} copy={copy} hoverXM={hoverXM} onHover={setHoverXM} />

      <div className="rc-diagram-row">
        <MomentDiagram model={model} copy={copy} hoverXM={hoverXM} onHover={setHoverXM} />
        <ShearDiagram model={model} copy={copy} hoverXM={hoverXM} onHover={setHoverXM} />
      </div>

      <div className="rc-readout" aria-live="polite">
        {readout ? (
          <>
            <p>
              <span className="engineering-result-label">x</span>
              {formatEngineeringNumber(readout.xM)} m
            </p>
            <p>
              <span className="engineering-result-label">M(x)</span>
              {formatEngineeringNumber(readout.momentKnM)} kN·m
            </p>
            <p>
              <span className="engineering-result-label">V(x)</span>
              {formatEngineeringNumber(readout.shearKn)} kN
            </p>
          </>
        ) : (
          <p className="muted">
            Hover or focus a diagram and use arrow keys to inspect x, M(x), and V(x). Support
            reactions are {formatEngineeringNumber(reaction)} kN each.
          </p>
        )}
      </div>

      <div className="rc-lower-row">
        <section className="rc-parameters" aria-label="Engineering parameters">
          <p className="engineering-result-label">Inputs / parameters</p>
          <EngineeringParameters copy={copy} />
        </section>
        <section aria-label="Analysis results">
          <p className="engineering-result-label">Results</p>
          <EngineeringResultsSummary copy={copy} />
        </section>
      </div>

      <div className="rc-cross-section">
        <BeamCrossSection model={model} copy={copy} />
      </div>

      <p className="muted chat-disclaimer">{copy.disclaimer}</p>
    </div>
  );
}
