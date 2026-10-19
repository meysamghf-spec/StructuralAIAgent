import { describe, expect, it } from "vitest";

import { revisionChains, type ApprovalSummary } from "@/lib/api";

const a = (id: string, rev: number, root: string | null, at: string, kind = "frame3d_analysis"): ApprovalSummary => ({
  id, project_id: "p", requester: "u", target_type: "DESIGN_DECISION", target_action: "engineering_run.approval",
  target_object_type: null, target_object_id: null, summary: id, status: "PENDING", approver: null,
  rejection_reason: null, requested_at: at, resolved_at: null,
  metadata: { module_kind: kind, revision: rev, root_approval_id: root },
});

describe("approval revision history", () => {
  it("groups revisions by root, ordered, newest chain first, ignoring non-run approvals", () => {
    const other = { ...a("x", 1, null, "2026-01-05"), metadata: {} };
    const chains = revisionChains([a("r2", 2, "r1", "2026-01-03"), a("r1", 1, null, "2026-01-01"), a("s1", 1, null, "2026-01-02", "aisc_steel_beam"), other]);
    expect(chains.map((c) => c.map((x) => x.id))).toEqual([["r1", "r2"], ["s1"]]);
  });
});
