import { afterEach, describe, expect, it, vi } from "vitest";

import { createApprovalRequest } from "@/lib/api";
import { visibleNavItems } from "@/lib/nav";

describe("frame3d design approval", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("POSTs a DESIGN_DECISION approval request for the project", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: "a1", status: "PENDING" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await createApprovalRequest("p1", { targetAction: "frame3d.design_approval", summary: "3D frame", metadata: { source: "frame3d" } });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/approvals");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toMatchObject({ project_id: "p1", target_type: "DESIGN_DECISION", target_action: "frame3d.design_approval" });
  });

  it("shows all completed pages in the sidebar", () => {
    const hrefs = visibleNavItems().map((i) => i.href);
    for (const h of ["/workspace/agents", "/workspace/agents/builder", "/workspace/memory", "/workspace/validation", "/workspace/integrations",
      "/workspace/optimization", "/workspace/learning", "/workspace/traceability", "/workspace/upgrades", "/workspace/ai", "/workspace/approvals"]) {
      expect(hrefs).toContain(h);
    }
  });
});
