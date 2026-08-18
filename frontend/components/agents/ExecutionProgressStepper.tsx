import {
  getActiveProgressIndex,
  getProgressLabel,
  getProgressSteps,
  getTerminalStepLabel,
  isTerminalProgress,
  type ProgressStep,
} from "@/lib/agent-workspace";
import type { AgentExecutionUserView } from "@/lib/api";

function stepState(
  index: number,
  activeIndex: number,
  progress: AgentExecutionUserView["progress"],
): "complete" | "active" | "upcoming" | "terminal-negative" {
  if (isTerminalProgress(progress) && index === 3) {
    if (progress === "completed") {
      return "complete";
    }
    return "terminal-negative";
  }
  if (index < activeIndex) {
    return "complete";
  }
  if (index === activeIndex) {
    return "active";
  }
  return "upcoming";
}

export function ExecutionProgressStepper({ progress }: { progress: AgentExecutionUserView["progress"] }) {
  const steps = getProgressSteps(progress);
  const activeIndex = getActiveProgressIndex(progress);
  const terminal = isTerminalProgress(progress);

  return (
    <div className="progress-stepper" aria-label={`Progress: ${getProgressLabel(progress)}`}>
      {steps.map((step: ProgressStep, index) => {
        const state = stepState(index, activeIndex, progress);
        const label =
          terminal && index === 3 && progress !== "completed"
            ? getTerminalStepLabel(progress)
            : step.label;

        return (
          <div key={step.key} className="progress-step-wrap">
            <div className={`progress-step ${state}`}>
              <span className="progress-dot" />
              <span className="progress-label">{label}</span>
            </div>
            {index < steps.length - 1 ? <span className="progress-line" aria-hidden="true" /> : null}
          </div>
        );
      })}
    </div>
  );
}
