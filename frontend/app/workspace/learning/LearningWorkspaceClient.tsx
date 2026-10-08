"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  approveLearningRecord,
  getLearningUsedByTask,
  listLearningRecords,
  rejectLearningRecord,
  reviewLearningRecord,
  type LearningRecordSummary,
  type LearningUseSummary,
} from "@/lib/api";
import {
  formatWorkspaceDate,
  getLearningScopeLabel,
  getLearningStatusLabel,
  truncateText,
} from "@/lib/workspace";
import { FormEvent, useCallback, useEffect, useState } from "react";

const OPEN_STATUSES = new Set(["CANDIDATE", "REVIEW"]);

export default function LearningWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [records, setRecords] = useState<LearningRecordSummary[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [taskId, setTaskId] = useState("");
  const [uses, setUses] = useState<LearningUseSummary[]>([]);
  const [useMessage, setUseMessage] = useState<string | null>(null);

  const refresh = useCallback(async (projectId: string) => {
    if (!projectId) {
      setRecords([]);
      return;
    }
    const response = await listLearningRecords(projectId);
    setRecords(response.records);
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      setError(null);
      refresh(selectedProjectId).catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load learning records"),
      );
    }
  }, [selectedProjectId, refresh, setError]);

  async function decide(recordId: string, action: "review" | "approve" | "reject") {
    if (!selectedProjectId) {
      return;
    }
    setBusyId(recordId);
    setError(null);
    try {
      if (action === "review") {
        await reviewLearningRecord(selectedProjectId, recordId);
      } else if (action === "approve") {
        await approveLearningRecord(selectedProjectId, recordId);
      } else {
        await rejectLearningRecord(selectedProjectId, recordId, "Rejected from the learning workspace");
      }
      await refresh(selectedProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Learning decision failed");
    } finally {
      setBusyId(null);
    }
  }

  async function lookupTask(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !taskId.trim()) {
      return;
    }
    setError(null);
    setUseMessage(null);
    try {
      const response = await getLearningUsedByTask(selectedProjectId, taskId.trim());
      setUses(response.uses);
      if (response.uses.length === 0) {
        setUseMessage("No approved learning was applied to this task.");
      }
    } catch (err) {
      setUses([]);
      setError(err instanceof Error ? err.message : "Failed to load learning used by this task");
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Experience</p>
        <h2>Engineering Learning</h2>
        <p className="subtitle">
          Approved experience can inform a later recommendation. It stays context only and does not
          replace the PEM, engineering rules, or QA.
        </p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
        description="Project learning stays inside this project. Engineer and approved global records follow their own scope."
      />

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <h3>Learning records</h3>
        {records.length === 0 ? <p className="muted">No learning records in this scope yet.</p> : null}
        <ul className="workspace-list">
          {records.map((record) => (
            <li key={record.id} className="workspace-list-item">
              <div>
                <span className="status-pill status-available">{getLearningScopeLabel(record.learning_scope)}</span>
                <span className="status-pill">{getLearningStatusLabel(record.approval_status)}</span>
                <p className="result-text">
                  {truncateText(record.engineering_reason || "Experience captured without a stated reason.", 280)}
                </p>
                <p className="muted">
                  QA {record.validation_result}
                  {record.agent_id ? ` · ${record.agent_id}` : ""}
                  {" · "}
                  {formatWorkspaceDate(record.created_at)}
                </p>
                <p className="muted">
                  Provenance: task {record.provenance.task_id}, agent {record.provenance.agent_id}, snapshot{" "}
                  {record.provenance.source_snapshot_id}, result {record.provenance.engineering_result_id}, decision{" "}
                  {record.provenance.human_decision}.
                </p>
                {record.provenance.source_element_ids.length > 0 ? (
                  <p className="muted">Elements: {record.provenance.source_element_ids.join(", ")}</p>
                ) : null}
                {OPEN_STATUSES.has(record.approval_status) ? (
                  <div className="approval-actions">
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busyId === record.id}
                      onClick={() => void decide(record.id, "review")}
                    >
                      Mark for review
                    </button>
                    <button
                      type="button"
                      className="button"
                      disabled={busyId === record.id}
                      onClick={() => void decide(record.id, "approve")}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busyId === record.id}
                      onClick={() => void decide(record.id, "reject")}
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>Why learning was used</h3>
        <p className="muted">
          Look up an assistant run to see which approved records were offered as context.
        </p>
        <form className="approval-form" onSubmit={(event) => void lookupTask(event)}>
          <input
            className="input"
            placeholder="Task or assistant run id"
            value={taskId}
            onChange={(event) => setTaskId(event.target.value)}
          />
          <button type="submit" className="button secondary">
            Show learning used
          </button>
        </form>
        {useMessage ? <p className="muted">{useMessage}</p> : null}
        <ul className="workspace-list">
          {uses.map((use) => (
            <li key={`${use.learning_record_id}-${use.created_at}`} className="workspace-list-item compact">
              <div>
                <strong>{use.learning_record_id}</strong>
                <p className="result-text">{use.explanation}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
