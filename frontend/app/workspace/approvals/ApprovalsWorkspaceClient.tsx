"use client";

import { ApprovalReviewPanel } from "@/components/agents/ApprovalReviewPanel";
import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { listApprovals, listPendingApprovals, type ApprovalSummary } from "@/lib/api";
import { formatWorkspaceDate, getApprovalStatusLabel, truncateText } from "@/lib/workspace";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function ApprovalsWorkspaceClient() {
  const searchParams = useSearchParams();
  const reviewId = searchParams.get("review");
  const { projects, selectedProjectId, setSelectedProjectId, selectedProject, loading, error, setError } =
    useProjectScope(searchParams.get("project"));

  const [pending, setPending] = useState<ApprovalSummary[]>([]);
  const [history, setHistory] = useState<ApprovalSummary[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async (projectId: string) => {
    if (!projectId) {
      setPending([]);
      setHistory([]);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const [pendingResponse, allResponse] = await Promise.all([
        listPendingApprovals(projectId),
        listApprovals(projectId),
      ]);
      setPending(pendingResponse.requests);
      setHistory(allResponse.requests.filter((item) => item.status !== "PENDING"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load approvals");
    } finally {
      setBusy(false);
    }
  }, [setError]);

  useEffect(() => {
    if (selectedProjectId) {
      void refresh(selectedProjectId);
    }
  }, [selectedProjectId, refresh]);

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Review</p>
        <h2>Approvals</h2>
        <p className="subtitle">
          Review engineering decisions that need your sign-off before the platform continues.
        </p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
        description="Approvals are always scoped to one project."
      />

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <h3>Waiting for your review</h3>
        {loading || busy ? <p className="muted">Loading approvals…</p> : null}
        {!loading && !busy && pending.length === 0 ? (
          <p className="muted">No approvals waiting right now.</p>
        ) : null}
        <ul className="workspace-list">
          {pending.map((item) => (
            <li key={item.id} className="workspace-list-item">
              <div>
                <strong>{item.summary}</strong>
                <p className="muted">
                  Requested by {item.requester} · {formatWorkspaceDate(item.requested_at)}
                </p>
                {item.target_object_type === "agent_execution" ? (
                  <p className="muted">
                    Linked assistant activity ·{" "}
                    <Link href={`/workspace/agents?project=${selectedProjectId}&review=${item.id}`}>
                      View in assistants
                    </Link>
                  </p>
                ) : null}
              </div>
              {(reviewId === null || reviewId === item.id) && selectedProjectId ? (
                <ApprovalReviewPanel
                  projectId={selectedProjectId}
                  approvalRequestId={item.id}
                  onResolved={() => void refresh(selectedProjectId)}
                />
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>Recent decisions</h3>
        {history.length === 0 ? <p className="muted">No completed approvals yet.</p> : null}
        <ul className="workspace-list">
          {history.map((item) => (
            <li key={item.id} className="workspace-list-item compact">
              <div>
                <strong>{item.summary}</strong>
                <p className="muted">
                  {getApprovalStatusLabel(item.status)}
                  {item.approver ? ` · ${item.approver}` : ""}
                  {" · "}
                  {formatWorkspaceDate(item.resolved_at ?? item.requested_at)}
                </p>
                {item.rejection_reason ? (
                  <p className="muted">{truncateText(item.rejection_reason)}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {selectedProject ? (
        <p className="muted">
          Reviewing approvals for <strong>{selectedProject.name}</strong>.
        </p>
      ) : null}
    </section>
  );
}
