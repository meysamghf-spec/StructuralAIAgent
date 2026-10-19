"use client";

import { ApprovalReviewPanel } from "@/components/agents/ApprovalReviewPanel";
import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { listApprovals, listPendingApprovals, revisionChains, type ApprovalSummary, type RevisionChange } from "@/lib/api";
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
  const [all, setAll] = useState<ApprovalSummary[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

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
      setAll(allResponse.requests);
      setHistory(allResponse.requests.filter((item) => item.status !== "PENDING"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load approvals");
    } finally {
      setBusy(false);
    }
  }, [setError]);

  const chains = revisionChains(all);

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
      {notice ? <div className="alert" role="status">{notice}</div> : null}

      <section className="card">
        <h3>Waiting for your review</h3>
        <p className="muted">
          Every chat analysis / design run creates an item here. Rejecting needs a reason (Persian or English); the
          reason is parsed (e.g. “increase column size”, “use Φ20”, “drift too high”, “cover 50 mm”), the model is
          re-run and a new revision is created.
        </p>
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
                  onResolved={(msg) => {
                    setNotice(msg ?? null);
                    void refresh(selectedProjectId);
                  }}
                />
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      {chains.length ? (
        <section className="card">
          <h3>Revision history</h3>
          <ul className="workspace-list">
            {chains.map((chain) => (
              <li key={chain[0].id} className="workspace-list-item compact">
                <div>
                  <strong>{String(chain[0].metadata?.module_label ?? "Engineering run")}</strong>
                  <ol className="revision-chain">
                    {chain.map((a) => {
                      const changes = (a.metadata?.changes as RevisionChange[] | undefined) ?? [];
                      return (
                        <li key={a.id}>
                          <span className="revision-badge">Rev {String(a.metadata?.revision ?? 1)}</span>{" "}
                          {getApprovalStatusLabel(a.status)} · {formatWorkspaceDate(a.requested_at)}
                          {a.metadata?.change_reason ? <p className="muted">Why: {String(a.metadata.change_reason)}</p> : null}
                          {changes.length ? (
                            <p className="muted">
                              Changed: {changes.map((c) => `${c.key} ${JSON.stringify(c.old)} → ${JSON.stringify(c.new)}`).join("; ")}
                            </p>
                          ) : null}
                          {a.rejection_reason ? <p className="muted">Rejected: {truncateText(a.rejection_reason)}</p> : null}
                        </li>
                      );
                    })}
                  </ol>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

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
