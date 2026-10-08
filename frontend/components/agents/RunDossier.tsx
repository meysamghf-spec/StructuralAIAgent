import { getValidationLabel } from "@/lib/agent-workspace";
import {
  buildRunDossier,
  calculationWasNotProduced,
  parameterPemIsNotAuthoritative,
} from "@/lib/engineering-workspace";
import type { AgentExecutionSummary } from "@/lib/api";
import { downloadProjectFile } from "@/lib/api";
import Link from "next/link";

export function RunDossier({ execution }: { execution: AgentExecutionSummary }) {
  const dossier = buildRunDossier(execution);
  const validationLabel = getValidationLabel(dossier.authoritative.validationStatus);

  return (
    <div className="run-dossier" aria-label="Engineering run record">
      <section>
        <p className="result-label">Request</p>
        <p className="result-text">{dossier.request ?? "No request text was stored."}</p>
      </section>

      <section>
        <p className="result-label">Agent result</p>
        <p className="result-text">{dossier.agentResult ?? "No engineering result yet."}</p>
      </section>

      <section className="approval-panel" aria-label="Authoritative project data">
        <strong>Authoritative project data</strong>
        <p className="muted">
          The current PEM, calculations, code checks, and QA stay authoritative. Approved learning is
          context only.
        </p>
        <p className="muted">
          PEM version {dossier.authoritative.pemVersion ?? "not recorded"}
          {dossier.authoritative.pemSnapshotId
            ? ` · snapshot ${dossier.authoritative.pemSnapshotId}`
            : ""}
        </p>
        <p className="muted">QA {validationLabel ?? dossier.authoritative.qaStatus ?? "not recorded"}</p>
        {parameterPemIsNotAuthoritative(execution) ? (
          <p className="muted">A requested PEM version was ignored. This run used the current project snapshot.</p>
        ) : null}
        <p className="muted">
          Learning overrides PEM: {dossier.authoritative.learningOverridesPem ? "yes" : "no"}
        </p>
      </section>

      <section aria-label="Engineering calculation">
        <p className="result-label">Calculation</p>
        {calculationWasNotProduced(dossier.engineering) ? (
          <p className="muted">
            No engineering calculation was produced
            {dossier.engineering.capabilityStatus ? ` (${dossier.engineering.capabilityStatus})` : ""}.
          </p>
        ) : (
          <p className="muted">
            {dossier.engineering.capabilityStatus
              ? `Capability ${dossier.engineering.capabilityStatus}.`
              : "No calculation record is attached to this run."}
          </p>
        )}
        {dossier.engineering.analysisRunId ? (
          <p className="muted">
            <Link href={`/workspace/analysis?project=${execution.project_id}`}>
              Analysis run {dossier.engineering.analysisRunId}
            </Link>
          </p>
        ) : null}
        {dossier.engineering.designRunId ? (
          <p className="muted">
            <Link href={`/workspace/design?project=${execution.project_id}`}>
              Design run {dossier.engineering.designRunId}
            </Link>
          </p>
        ) : null}
        {dossier.engineering.resultSetId ? (
          <p className="muted">
            <Link href={`/workspace/results?project=${execution.project_id}`}>
              Result set {dossier.engineering.resultSetId}
            </Link>
          </p>
        ) : null}
        {dossier.engineering.resultValidationStatus ? (
          <p className="muted">Result validation {dossier.engineering.resultValidationStatus}</p>
        ) : null}
        {dossier.engineering.solver ? (
          <p className="muted">
            {dossier.engineering.solver}{" "}
            {dossier.engineering.solverStatus === "REQUIRES_LOCAL_SOFTWARE" ||
            dossier.engineering.solverStatus === "NOT_INSTALLED" ||
            dossier.engineering.solverStatus === "NOT_ACCESSIBLE"
              ? "was not executed. Local engineering software is not available in this environment."
              : `status ${dossier.engineering.solverStatus ?? "recorded"}.`}
            {dossier.engineering.integrationExecutionId
              ? ` Integration ${dossier.engineering.integrationExecutionId}.`
              : ""}{" "}
            <Link href={`/workspace/integrations?project=${execution.project_id}`}>Open integrations</Link>
          </p>
        ) : null}
      </section>

      <section aria-label="Learning context">
        <p className="result-label">Learning context</p>
        {dossier.learning ? (
          <ul className="workspace-list">
            {dossier.learning.records.map((record) => (
              <li key={record.id} className="workspace-list-item compact">
                <span className="status-pill">Context only</span>
                <p className="result-text">{record.explanation}</p>
                <p className="muted">{record.learning_scope}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No approved learning was attached to this run.</p>
        )}
      </section>

      <section aria-label="Provenance">
        <p className="result-label">Provenance</p>
        <p className="muted">
          Run {dossier.provenance.runId} · agent {dossier.provenance.agentId} · version{" "}
          {dossier.provenance.agentVersion ?? "unrecorded"}
          {dossier.provenance.agentVersionId ? ` (${dossier.provenance.agentVersionId})` : ""}
        </p>
        <p className="muted">Project {dossier.provenance.projectId}</p>
        {dossier.provenance.learningRecordIds.length > 0 ? (
          <p className="muted">Learning records {dossier.provenance.learningRecordIds.join(", ")}</p>
        ) : null}
      </section>

      <section aria-label="Attachments">
        <p className="result-label">Attachments</p>
        {dossier.attachments.length === 0 ? (
          <p className="muted">No project files were attached.</p>
        ) : (
          <ul className="workspace-list">
            {dossier.attachments.map((attachment) => (
              <li key={attachment.fileId} className="workspace-list-item compact">
                <button
                  className="button secondary"
                  type="button"
                  onClick={() =>
                    void downloadProjectFile(execution.project_id, attachment.fileId, attachment.filename)
                  }
                >
                  Download {attachment.filename}
                </button>
                <p className="muted">
                  {attachment.availability ?? "stored"}
                  {attachment.limitation ? ` · ${attachment.limitation}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Outputs">
        <p className="result-label">Outputs</p>
        {dossier.artifacts.length === 0 ? (
          <p className="muted">This run did not store a generated file.</p>
        ) : (
          <ul className="workspace-list">
            {dossier.artifacts.map((artifact) => (
              <li key={artifact.label} className="workspace-list-item compact">
                {artifact.href ? <Link href={artifact.href}>{artifact.label}</Link> : <span>{artifact.label}</span>}
                {artifact.detail ? <p className="muted">{artifact.detail}</p> : null}
              </li>
            ))}
          </ul>
        )}
        <p className="muted">
          <Link href={`/workspace/cad?project=${execution.project_id}`}>Open drawing workspace</Link>
        </p>
      </section>

      {dossier.approval.required ? (
        <section aria-label="Approval">
          <p className="result-label">Approval</p>
          <p className="muted">
            {dossier.approval.progress === "awaiting_approval"
              ? "Waiting for an engineer decision."
              : "This run required approval."}
            {dossier.approval.requestId ? ` Request ${dossier.approval.requestId}.` : ""}
          </p>
        </section>
      ) : null}

      {dossier.errors.length > 0 ? (
        <div className="alert error">
          {dossier.errors.map((error) => (
            <p key={error}>{error}</p>
          ))}
        </div>
      ) : null}
      {dossier.warnings.length > 0 ? (
        <div className="alert">
          {dossier.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
