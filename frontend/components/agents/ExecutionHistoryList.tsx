import { RunDossier } from "@/components/agents/RunDossier";
import { ExecutionProgressStepper } from "@/components/agents/ExecutionProgressStepper";
import { ApprovalReviewPanel } from "@/components/agents/ApprovalReviewPanel";
import { RequestPlanPanel } from "@/components/agents/RequestPlanPanel";
import {
  approvedExperienceForExecution,
  formatDate,
  getProgressLabel,
  getValidationLabel,
  learningProvenancePath,
  summarizeExecution,
} from "@/lib/agent-workspace";
import { getLearningScopeLabel } from "@/lib/workspace";
import type { AgentExecutionSummary } from "@/lib/api";
import Link from "next/link";

function ExecutionResult({
  execution,
  projectId,
}: {
  execution: AgentExecutionSummary;
  projectId: string;
}) {
  const { hasResult, reportAvailable } = summarizeExecution(execution);
  const validationLabel = getValidationLabel(execution.validation_status);

  if (!hasResult && execution.user_view.progress !== "awaiting_approval") {
    return null;
  }

  return (
    <div className="execution-result">
      {execution.user_view.final_result ? (
        <>
          <p className="result-label">Result</p>
          <p className="result-text">{execution.user_view.final_result}</p>
        </>
      ) : null}
      {validationLabel ? <p className="muted validation-line">{validationLabel}</p> : null}
      {reportAvailable ? (
        <p className="muted report-line">Decision history report saved to this project.</p>
      ) : null}
      <LearningContext execution={execution} projectId={projectId} />
    </div>
  );
}

function LearningContext({
  execution,
  projectId,
}: {
  execution: AgentExecutionSummary;
  projectId: string;
}) {
  const experience = approvedExperienceForExecution(execution);
  if (!experience) {
    return null;
  }

  return (
    <section className="approval-panel" aria-label="Approved engineering experience">
      <div className="approval-panel-header">
        <strong>{experience.heading}</strong>
        <p className="muted">
          Context only ({experience.authority}). These records are not the engineering result and do not
          replace the PEM, calculations, or QA.
        </p>
      </div>
      <ul className="workspace-list">
        {experience.records.map((record) => (
          <li key={record.id} className="workspace-list-item compact">
            <div>
              <span className="status-pill">{getLearningScopeLabel(record.learning_scope)}</span>
              <span className="status-pill">Context only</span>
              <p className="result-text">{record.explanation}</p>
              <p className="muted">
                <Link href={learningProvenancePath(projectId, record.id)}>Provenance {record.id}</Link>
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ExecutionHistoryList({
  executions,
  projectId,
  reviewApprovalId,
  onRefresh,
  selectedExecutionId,
  onSelectExecution,
}: {
  executions: AgentExecutionSummary[];
  projectId: string;
  reviewApprovalId: string | null;
  onRefresh: () => void;
  selectedExecutionId?: string | null;
  onSelectExecution?: (executionId: string) => void;
}) {
  if (executions.length === 0) {
    return <p className="muted">No assistant activity yet for this project.</p>;
  }

  return (
    <ul className="execution-list">
      {executions.map((execution) => {
        const summary = summarizeExecution(execution);
        const showReview =
          execution.user_view.requires_approval &&
          execution.user_view.approval_request_id &&
          (reviewApprovalId === null || reviewApprovalId === execution.user_view.approval_request_id);

        return (
          <li key={execution.id} className="card execution-card">
            <div className="execution-card-header">
              <div>
                <h4>{summary.title}</h4>
                <p className="muted">{formatDate(execution.created_at)}</p>
              </div>
              <span className={`progress-badge progress-${execution.user_view.progress}`}>
                {getProgressLabel(execution.user_view.progress)}
              </span>
            </div>
            {onSelectExecution ? (
              <button
                className="button secondary"
                type="button"
                onClick={() => onSelectExecution(execution.id)}
              >
                {selectedExecutionId === execution.id ? "Run record open" : "Open run record"}
              </button>
            ) : null}

            <ExecutionProgressStepper progress={execution.user_view.progress} />

            {execution.prompt_generation ? (
              <RequestPlanPanel plan={execution.prompt_generation} />
            ) : null}

            {showReview && execution.user_view.approval_request_id ? (
              <ApprovalReviewPanel
                projectId={projectId}
                approvalRequestId={execution.user_view.approval_request_id}
                onResolved={onRefresh}
              />
            ) : null}

            <ExecutionResult execution={execution} projectId={projectId} />
            {selectedExecutionId === execution.id ? <RunDossier execution={execution} /> : null}
          </li>
        );
      })}
    </ul>
  );
}
