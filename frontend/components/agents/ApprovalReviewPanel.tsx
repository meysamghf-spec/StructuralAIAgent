"use client";

import { useAuth } from "@/hooks/useAuth";
import { approveAgentRequest, getApprovalRequest, rejectAgentRequest } from "@/lib/api";
import { getApprovalReviewPath } from "@/lib/agent-workspace";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

export function ApprovalReviewPanel({
  projectId,
  approvalRequestId,
  onResolved,
}: {
  projectId: string;
  approvalRequestId: string;
  onResolved: (message?: string) => void;
}) {
  const { user } = useAuth();
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolvedStatus, setResolvedStatus] = useState<string | null>(null);

  // A chat message can outlive the decision (or be clicked twice): always check the real state first.
  const syncStatus = useCallback(async () => {
    try {
      const current = await getApprovalRequest(projectId, approvalRequestId);
      setResolvedStatus(current.status !== "PENDING" ? current.status : null);
      return current.status;
    } catch {
      return null;
    }
  }, [projectId, approvalRequestId]);

  useEffect(() => {
    void syncStatus();
  }, [syncStatus]);

  async function recoverFromConflict(err: unknown, fallback: string) {
    const status = await syncStatus();
    if (status && status !== "PENDING") {
      setError(null);
      onResolved();
      return;
    }
    setError(err instanceof Error ? err.message : fallback);
  }

  async function handleApprove(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await approveAgentRequest(projectId, approvalRequestId, note || undefined);
      onResolved();
    } catch (err) {
      await recoverFromConflict(err, "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleReject(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) {
      setError("Please provide a reason for rejection.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await rejectAgentRequest(projectId, approvalRequestId, reason.trim());
      onResolved(res?.revision_message ?? undefined);
    } catch (err) {
      await recoverFromConflict(err, "Rejection failed");
    } finally {
      setBusy(false);
    }
  }

  if (resolvedStatus) {
    const label = resolvedStatus.charAt(0) + resolvedStatus.slice(1).toLowerCase();
    return (
      <section className="approval-panel approval-panel-resolved" data-testid="approval-resolved">
        <strong>Decision recorded: {label}</strong>
        <p className="muted">
          This item was already {label.toLowerCase()}, so no further action is needed.{" "}
          <Link className="text-link" href={getApprovalReviewPath(projectId, approvalRequestId)}>
            Open in Approvals
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="approval-panel">
      <div className="approval-panel-header">
        <strong>Review required</strong>
        <p className="muted">
          This work needs engineer approval before results are finalized. Decisions are recorded
          under your authenticated account
          {user ? ` (${user.email})` : ""}.
        </p>
        <Link className="text-link" href={getApprovalReviewPath(projectId, approvalRequestId)}>
          Open review link
        </Link>
      </div>

      {error ? <div className="alert error">{error}</div> : null}

      <div className="approval-actions">
        <form className="approval-form" onSubmit={handleApprove}>
          <h4>Approve</h4>
          <input
            className="input"
            placeholder="Optional note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          <button className="button" type="submit" disabled={busy}>
            Approve result
          </button>
        </form>

        <form className="approval-form" onSubmit={handleReject}>
          <h4>Reject</h4>
          <input
            className="input"
            placeholder="Rejection reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <button className="button secondary" type="submit" disabled={busy}>
            Reject result
          </button>
        </form>
      </div>
    </section>
  );
}
