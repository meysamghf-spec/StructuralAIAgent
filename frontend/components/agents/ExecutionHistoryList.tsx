import { ExecutionProgressStepper } from "@/components/agents/ExecutionProgressStepper";
import { ApprovalReviewPanel } from "@/components/agents/ApprovalReviewPanel";
import {
  formatDate,
  getProgressLabel,
  getValidationLabel,
  summarizeExecution,
} from "@/lib/agent-workspace";
import type { AgentExecutionSummary } from "@/lib/api";

function ExecutionResult({ execution }: { execution: AgentExecutionSummary }) {
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
    </div>
  );
}

export function ExecutionHistoryList({
  executions,
  projectId,
  reviewApprovalId,
  onRefresh,
}: {
  executions: AgentExecutionSummary[];
  projectId: string;
  reviewApprovalId: string | null;
  onRefresh: () => void;
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

            <ExecutionProgressStepper progress={execution.user_view.progress} />

            {showReview && execution.user_view.approval_request_id ? (
              <ApprovalReviewPanel
                projectId={projectId}
                approvalRequestId={execution.user_view.approval_request_id}
                onResolved={onRefresh}
              />
            ) : null}

            <ExecutionResult execution={execution} />
          </li>
        );
      })}
    </ul>
  );
}
