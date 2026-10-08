import { describe, expect, it } from "vitest";
import type { AssistantProfile } from "../lib/agent-workspace";
import {
  buildRunDossier,
  filesForProject,
  parameterPemIsNotAuthoritative,
  productionRunAllowed,
} from "../lib/engineering-workspace";
import type { AgentExecutionSummary, ProjectFileSummary } from "../lib/api";

const profile = (status: AssistantProfile["status"]): AssistantProfile => ({
  id: "analysis",
  title: "Structural Analysis Assistant",
  description: "Analysis",
  capabilities: ["Analysis review"],
  status,
  agentType: "ANALYSIS_AGENT",
});

function execution(overrides: Partial<AgentExecutionSummary> = {}): AgentExecutionSummary {
  return {
    id: "run-1",
    project_id: "project-1",
    agent_definition_id: "agent-1",
    agent_version: 3,
    execution_status: "COMPLETED",
    approval_request_id: null,
    validation_status: "NOT_CHECKED",
    created_by: "engineer",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    user_view: {
      progress: "completed",
      requires_approval: false,
      approval_request_id: null,
      final_result: "Drift was not available in the PEM.",
      summary: "Analyze the lateral system",
    },
    input_request: {
      user_request: "Analyze the lateral system",
      parameters: {
        pem_version: 99,
        attachment_context: {
          attachments: [
            {
              file_id: "file-1",
              filename: "notes.pdf",
              availability: "stored_only",
              limitation: "Stored for reference.",
            },
          ],
        },
      },
    },
    output: {
      learning_overrides_pem: false,
      learning_overrides_rules: false,
      learning_overrides_qa: false,
    },
    traceability_metadata: {
      project_id: "project-1",
      agent_id: "agent-1",
      agent_version: 3,
      agent_version_id: "version-3",
      run_id: "run-1",
      pem_version: 1,
      pem_snapshot_id: "snapshot-1",
      qa_status: "NOT_CHECKED",
      learning_record_ids: ["learning-1"],
      attachment_file_ids: ["file-1"],
      approved_engineering_experience: {
        heading: "APPROVED ENGINEERING EXPERIENCE — CONTEXT ONLY",
        authority: "CONTEXT_ONLY",
        records: [
          {
            id: "learning-1",
            learning_scope: "PROJECT",
            applicability: {},
            explanation: "Use the project checklist.",
            authority: "CONTEXT_ONLY",
          },
        ],
      },
    },
    agent_result: {
      structured_output: { learning_overrides_pem: false },
      generated_artifacts: [
        {
          name: "RC beam Demo analysis",
          description: "Demonstration only.",
          href: "https://example.invalid/secret",
        },
      ],
    },
    ...overrides,
  };
}

describe("engineering workspace", () => {
  it("allows only available agents to start a production run", () => {
    expect(productionRunAllowed(null)).toBe(true);
    expect(productionRunAllowed(profile("Available"))).toBe(true);
    expect(productionRunAllowed(profile("In setup"))).toBe(false);
    expect(productionRunAllowed(profile("Unavailable"))).toBe(false);
  });

  it("keeps files from another project out of the attachment list", () => {
    const files: ProjectFileSummary[] = [
      {
        id: "own",
        project_id: "project-1",
        filename: "own.pdf",
        file_type: "PDF",
        parsing_status: "COMPLETE",
        extraction_status: "COMPLETE",
        upload_time: "2026-01-01T00:00:00Z",
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "other",
        project_id: "project-2",
        filename: "other.pdf",
        file_type: "PDF",
        parsing_status: "COMPLETE",
        extraction_status: "COMPLETE",
        upload_time: "2026-01-01T00:00:00Z",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    expect(filesForProject(files, "project-1").map((file) => file.id)).toEqual(["own"]);
  });

  it("separates the request, result, PEM, learning, and QA", () => {
    const dossier = buildRunDossier(execution());
    expect(dossier.request).toBe("Analyze the lateral system");
    expect(dossier.agentResult).toContain("PEM");
    expect(dossier.authoritative.pemVersion).toBe(1);
    expect(dossier.authoritative.pemSnapshotId).toBe("snapshot-1");
    expect(dossier.authoritative.learningOverridesPem).toBe(false);
    expect(dossier.learning?.authority).toBe("CONTEXT_ONLY");
    expect(dossier.learning?.records[0]?.explanation).not.toBe(dossier.agentResult);
    expect(dossier.provenance.agentVersionId).toBe("version-3");
    expect(dossier.provenance.learningRecordIds).toEqual(["learning-1"]);
    expect(dossier.attachments[0]?.filename).toBe("notes.pdf");
    expect(dossier.artifacts[0]?.href).toBeNull();
    expect(parameterPemIsNotAuthoritative(execution())).toBe(true);
  });

  it("reports a learning override instead of treating it as the PEM", () => {
    const dossier = buildRunDossier(
      execution({
        output: { learning_overrides_pem: true },
      }),
    );
    expect(dossier.authoritative.learningOverridesPem).toBe(true);
    expect(dossier.errors.some((error) => error.includes("not authoritative"))).toBe(true);
  });
});
