"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApprovalReviewPanel } from "@/components/agents/ApprovalReviewPanel";
import {
  getProjectApprovalSummary,
  listPendingApprovals,
  type ApprovalSummary,
  type ProjectApprovalSummary,
} from "@/lib/api";

const STATE_LABEL: Record<ProjectApprovalSummary["state"], string> = {
  approved: "Approved",
  pending: "Waiting for your decision",
  needs_revision: "Needs revision",
  no_runs: "Nothing to approve yet",
};

/** Project approval status with the exact reasons it is not approved, and the chat-run items to decide on. */
export function ProjectApprovalCard({ projectId, refreshKey = 0, showPending = true }: { projectId: string; refreshKey?: number; showPending?: boolean }) {
  const [summary, setSummary] = useState<ProjectApprovalSummary | null>(null);
  const [pending, setPending] = useState<ApprovalSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!projectId) {
      return;
    }
    try {
      const [s, p] = await Promise.all([getProjectApprovalSummary(projectId), listPendingApprovals(projectId)]);
      setSummary(s);
      setPending(p.requests);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load approval status");
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (!projectId) {
    return null;
  }
  return (
    <section className="card project-approval-card" data-testid="project-approval-card">
      <div className="agent-card-header">
        <h3>Project approval</h3>
        {summary ? (
          <span className={`status-pill status-${summary.project_approved ? "available" : "unavailable"}`}>
            {STATE_LABEL[summary.state]}
          </span>
        ) : null}
      </div>
      {error ? <div className="alert error">{error}</div> : null}
      {summary ? (
        <>
          <p className="muted">
            {summary.counts.approved} approved · {summary.counts.pending} pending · {summary.counts.rejected} rejected
          </p>
          {summary.blockers.length ? (
            <ul className="feature-list" aria-label="Why this project is not approved">
              {summary.blockers.map((b) => (
                <li key={b.code}>
                  {b.en}
                  <br />
                  <span dir="rtl" className="muted">{b.fa}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>All engineering runs are approved.</p>
          )}
        </>
      ) : null}
      {(showPending ? pending : []).map((item) => (
        <div key={item.id} className="workspace-list-item">
          <strong>{item.summary}</strong>
          <ApprovalReviewPanel
            projectId={projectId}
            approvalRequestId={item.id}
            onResolved={() => void load()}
          />
        </div>
      ))}
      <Link className="text-link" href={`/workspace/approvals?project=${projectId}`}>
        Open Approvals
      </Link>
    </section>
  );
}
