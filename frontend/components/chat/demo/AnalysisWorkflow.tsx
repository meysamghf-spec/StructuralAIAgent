const STEPS = [
  "Input parsed",
  "Beam model created",
  "Analysis completed",
  "Results verified",
] as const;

export function AnalysisWorkflow() {
  return (
    <ol className="rc-workflow" aria-label="Completed analysis workflow">
      {STEPS.map((step) => (
        <li key={step}>
          <span aria-hidden="true">✓</span>
          {step}
        </li>
      ))}
    </ol>
  );
}
