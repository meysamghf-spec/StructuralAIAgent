import {
  approvedExperienceForExecution,
  type ApprovedEngineeringExperience,
  type AssistantProfile,
} from "./agent-workspace";
import type { AgentExecutionSummary, ProjectFileSummary } from "./api";

export type RunAttachment = {
  fileId: string;
  filename: string;
  availability: string | null;
  limitation: string | null;
  projectId: string | null;
};

export type RunArtifact = {
  label: string;
  detail: string | null;
  href: string | null;
};

export type EngineeringChain = {
  analysisRunId: string | null;
  designRunId: string | null;
  optimizationRunId: string | null;
  resultSetId: string | null;
  resultValidationStatus: string | null;
  capabilityStatus: string | null;
  engineeringResultsAvailable: boolean | null;
  solver: string | null;
  solverStatus: string | null;
  integrationExecutionId: string | null;
};

export type RunDossier = {
  request: string | null;
  agentResult: string | null;
  authoritative: {
    pemVersion: number | string | null;
    pemSnapshotId: string | null;
    qaStatus: string | null;
    validationStatus: string | null;
    learningOverridesPem: boolean;
    learningOverridesRules: boolean;
    learningOverridesQa: boolean;
  };
  learning: ApprovedEngineeringExperience | null;
  engineering: EngineeringChain;
  approval: {
    required: boolean;
    requestId: string | null;
    progress: string;
  };
  provenance: {
    projectId: string | null;
    agentId: string | null;
    agentVersionId: string | null;
    agentVersion: number | string | null;
    runId: string | null;
    learningRecordIds: string[];
    attachmentFileIds: string[];
  };
  attachments: RunAttachment[];
  artifacts: RunArtifact[];
  errors: string[];
  warnings: string[];
};

export function productionRunAllowed(profile: AssistantProfile | null): boolean {
  return profile === null || profile.status === "Available";
}

export function filesForProject(
  files: ProjectFileSummary[],
  projectId: string,
): ProjectFileSummary[] {
  return files.filter((file) => !file.project_id || file.project_id === projectId);
}

export function buildRunDossier(execution: AgentExecutionSummary): RunDossier {
  const trace = record(execution.traceability_metadata);
  const parameters = record(execution.input_request?.parameters);
  const output = record(execution.output);
  const structured = record(execution.agent_result?.structured_output);
  const validationInfo = record(execution.agent_result?.validation_information);
  const experience = approvedExperienceForExecution(execution);

  const pemVersion = firstDefined(trace.pem_version, execution.context_snapshot?.pem_version);
  const pemSnapshotId = text(firstDefined(trace.pem_snapshot_id, execution.context_snapshot?.pem_snapshot_id));
  const learningOverridesPem = flag(output.learning_overrides_pem) || flag(structured.learning_overrides_pem);
  const learningOverridesRules =
    flag(output.learning_overrides_rules) || flag(structured.learning_overrides_rules);
  const learningOverridesQa = flag(output.learning_overrides_qa) || flag(structured.learning_overrides_qa);

  return {
    request: text(execution.input_request?.user_request) ?? execution.user_view.summary,
    agentResult: execution.user_view.final_result,
    authoritative: {
      pemVersion: pemVersion === undefined ? null : (pemVersion as number | string),
      pemSnapshotId,
      qaStatus: text(trace.qa_status) ?? execution.validation_status,
      validationStatus: execution.validation_status,
      learningOverridesPem,
      learningOverridesRules,
      learningOverridesQa,
    },
    learning: experience,
    engineering: engineeringChain(trace, structured),
    approval: {
      required: execution.user_view.requires_approval,
      requestId: execution.user_view.approval_request_id,
      progress: execution.user_view.progress,
    },
    provenance: {
      projectId: text(trace.project_id) ?? execution.project_id,
      agentId: text(trace.agent_id) ?? execution.agent_definition_id,
      agentVersionId: text(trace.agent_version_id),
      agentVersion: (trace.agent_version as number | string | undefined) ?? execution.agent_version,
      runId: text(trace.run_id) ?? execution.id,
      learningRecordIds: stringList(trace.learning_record_ids),
      attachmentFileIds: stringList(trace.attachment_file_ids),
    },
    attachments: attachmentsFrom(parameters, execution.project_id),
    artifacts: artifactsFrom(execution),
    errors: errorsFrom(execution, learningOverridesPem),
    warnings: warningsFrom(validationInfo, parameters),
  };
}

export function parameterPemIsNotAuthoritative(execution: AgentExecutionSummary): boolean {
  const trace = record(execution.traceability_metadata);
  const parameters = record(execution.input_request?.parameters);
  if (parameters.pem_version === undefined || trace.pem_version === undefined) {
    return false;
  }
  return String(parameters.pem_version) !== String(trace.pem_version);
}

function engineeringChain(
  trace: Record<string, unknown>,
  structured: Record<string, unknown>,
): EngineeringChain {
  return {
    analysisRunId: text(firstDefined(trace.analysis_run_id, structured.analysis_run_id)),
    designRunId: text(firstDefined(trace.design_run_id, structured.design_run_id)),
    optimizationRunId: text(firstDefined(trace.optimization_run_id, structured.optimization_run_id)),
    resultSetId: text(firstDefined(trace.result_set_id, structured.result_set_id)),
    resultValidationStatus: text(
      firstDefined(trace.result_validation_status, structured.result_validation_status),
    ),
    capabilityStatus: text(firstDefined(trace.capability_status, structured.capability_status)),
    engineeringResultsAvailable: availabilityFlag(
      firstDefined(trace.engineering_results_available, structured.engineering_results_available),
    ),
    solver: text(firstDefined(trace.solver, structured.solver)),
    solverStatus: text(firstDefined(trace.solver_status, structured.solver_status)),
    integrationExecutionId: text(
      firstDefined(trace.integration_execution_id, structured.integration_execution_id),
    ),
  };
}

function attachmentsFrom(
  parameters: Record<string, unknown>,
  projectId: string,
): RunAttachment[] {
  const bundle = record(parameters.attachment_context);
  const raw = bundle.attachments;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }
    const entry = item as Record<string, unknown>;
    const fileId = text(entry.file_id);
    const filename = text(entry.filename);
    if (!fileId || !filename) {
      return [];
    }
    return [
      {
        fileId,
        filename,
        availability: text(entry.availability),
        limitation: text(entry.limitation),
        projectId,
      },
    ];
  });
}

function artifactsFrom(execution: AgentExecutionSummary): RunArtifact[] {
  const raw = execution.agent_result?.generated_artifacts;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }
    const artifact = item as Record<string, unknown>;
    const label = text(artifact.name) ?? text(artifact.type);
    if (!label) {
      return [];
    }
    const href = text(artifact.href);
    return [
      {
        label,
        detail: text(artifact.description),
        href: href && href.startsWith("/") ? href : null,
      },
    ];
  });
}

function errorsFrom(execution: AgentExecutionSummary, learningOverridesPem: boolean): string[] {
  const errors: string[] = [];
  const metadata = record(execution.error_metadata);
  const message = text(metadata.message);
  if (message) {
    errors.push(message);
  }
  if (learningOverridesPem) {
    errors.push("Learning was recorded as overriding the PEM. That result is not authoritative.");
  }
  if (execution.user_view.progress === "failed" && !message) {
    errors.push("The run failed before it produced an engineering result.");
  }
  return errors;
}

function warningsFrom(
  validationInfo: Record<string, unknown>,
  parameters: Record<string, unknown>,
): string[] {
  const warnings: string[] = [];
  const raw = validationInfo.warnings;
  if (Array.isArray(raw)) {
    for (const item of raw) {
      const value = text(item);
      if (value) {
        warnings.push(value);
      }
    }
  }
  const bundle = record(parameters.attachment_context);
  const attachments = bundle.attachments;
  if (Array.isArray(attachments)) {
    for (const item of attachments) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const entry = item as Record<string, unknown>;
      const limitation = text(entry.limitation);
      if (limitation) {
        warnings.push(`${text(entry.filename) ?? "Attachment"}: ${limitation}`);
      }
    }
  }
  return warnings;
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function text(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    const entry = text(item);
    return entry ? [entry] : [];
  });
}

function flag(value: unknown): boolean {
  return value === true;
}

function availabilityFlag(value: unknown): boolean | null {
  if (value === true || value === false) {
    return value;
  }
  return null;
}

function firstDefined(...values: unknown[]): unknown {
  return values.find((value) => value !== undefined && value !== null);
}
