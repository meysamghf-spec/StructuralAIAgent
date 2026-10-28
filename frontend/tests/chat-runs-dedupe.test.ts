import { describe, expect, it } from "vitest";
import { incompleteFrameRun, isUsableFrameRun, type ChatRun } from "../lib/chat-runs";


const base = { conversation_id: "c", conversation_title: "t", created_at: "2026-10-23T00:00:00Z", label: "x", summary: {} };
const full = { storeys: 3, bays_x: 2, bays_y: 2, bay_x_m: 5, bay_y_m: 5 };
const run = (over: Partial<ChatRun>): ChatRun => ({ ...base, message_id: Math.random().toString(), kind: "frame3d_analysis", status: "completed", inputs: full, ...over });

describe("results page frame analysis is shown once", () => {
  it("a run with missing bays is not usable and is offered for inline completion", () => {
    const bad = run({ status: "MISSING_REQUIRED_INPUT", inputs: { storeys: 3, bays_x: null, bays_y: null } });
    expect(isUsableFrameRun(bad)).toBe(false);
    expect(incompleteFrameRun([run({ kind: "autocad", inputs: null }), bad])).toBe(bad);
  });
  it("does not duplicate when a complete run exists (that result is what the page shows)", () => {
    const bad = run({ status: "MISSING_REQUIRED_INPUT", inputs: { storeys: 3 } });
    expect(incompleteFrameRun([bad, run({})])).toBeNull();
  });
  it("is null when there are no frame runs", () => {
    expect(incompleteFrameRun([run({ kind: "autocad", inputs: null })])).toBeNull();
  });
});

import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("results page wiring", () => {
  it("hides frame3d_analysis in the chat-runs list and keeps one frame section", () => {
    const src = readFileSync(join(__dirname, "../app/workspace/results/page.tsx"), "utf8");
    expect(src).toMatch(/excludeKinds=\{\["frame3d_analysis"\]\}/);
    expect((src.match(/<Frame3dWorkspacePanel/g) ?? []).length).toBe(1);
  });
});
