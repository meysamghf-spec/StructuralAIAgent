import type { VisualizationCopy } from "@/lib/rc-beam-visualization";

type EngineeringParametersProps = {
  copy: VisualizationCopy;
};

export function EngineeringParameters({ copy }: EngineeringParametersProps) {
  return (
    <dl className="rc-parameter-grid">
      <div>
        <dt>Span</dt>
        <dd>{copy.spanLabel}</dd>
      </div>
      <div>
        <dt>Uniform load</dt>
        <dd>{copy.loadLabel}</dd>
      </div>
      {copy.sectionLabel ? (
        <div>
          <dt>Section b × h</dt>
          <dd>{copy.sectionLabel}</dd>
        </div>
      ) : null}
      {copy.depthLabel ? (
        <div>
          <dt>Effective depth d</dt>
          <dd>{copy.depthLabel}</dd>
        </div>
      ) : null}
      {copy.fcLabel ? (
        <div>
          <dt>Concrete fc</dt>
          <dd>{copy.fcLabel}</dd>
        </div>
      ) : null}
      {copy.fyLabel ? (
        <div>
          <dt>Steel fy</dt>
          <dd>{copy.fyLabel}</dd>
        </div>
      ) : null}
      <div>
        <dt>Support</dt>
        <dd>Simply supported</dd>
      </div>
      <div>
        <dt>Loading</dt>
        <dd>Uniformly distributed</dd>
      </div>
    </dl>
  );
}
