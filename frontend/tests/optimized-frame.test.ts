import { beforeEach, describe, expect, it, vi } from "vitest";

let store: Record<string, string> = {};
vi.stubGlobal("window", {
  localStorage: { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => void (store[k] = v), removeItem: (k: string) => void delete store[k] },
  dispatchEvent: () => true,
});
vi.stubGlobal("CustomEvent", class { constructor(public type: string) {} });

import { mapOptimizationFull } from "@/lib/chat-mappers";
import type { ChatRun } from "@/lib/chat-runs";
import { loadFrame3dInputs, loadFrame3dPayload } from "@/lib/frame3d-store";
import { applyOptimizedFrame, loadOptFrame, originalOf, pendingOptimizedRun, runMarker, setOptView } from "@/lib/optimized-frame";

const geo = { storeys: 3, bays_x: 3, bays_y: 3, bay_x_m: 5, bay_y_m: 5, storey_height_m: 3.2 };
const optInputs = { ...geo, group_sections: { C1: [0.4, 0.45], B1: [0.25, 0.6] } };
const run = (o: Partial<ChatRun>): ChatRun => ({
  message_id: "m", conversation_id: "c", conversation_title: "", created_at: "2026-11-03T10:00:00Z",
  kind: "frame3d_analysis", label: "", status: "completed", inputs: geo, summary: {}, ...o,
});

describe("optimized frame → Model page", () => {
  beforeEach(() => { store = {}; });

  it("applies optimized inputs + payload and toggles back to the original", () => {
    applyOptimizedFrame("p1", { inputs: optInputs, payload: { kind: "frame3d_analysis" }, original: geo, marker: "x" });
    expect(loadFrame3dInputs("p1")).toEqual(optInputs);
    expect(loadFrame3dPayload("p1")).toEqual({ kind: "frame3d_analysis" });
    expect(loadOptFrame("p1")?.view).toBe("optimized");
    expect(setOptView("p1", "original")).toEqual(geo);
    expect(loadOptFrame("p1")?.view).toBe("original");
    expect(setOptView("p1", "optimized")).toEqual(optInputs);
  });

  it("original falls back to inputs without group_sections", () => {
    expect(originalOf(optInputs)).toEqual(geo);
  });

  it("picks a newer optimized chat run only once", () => {
    const runs = [run({ message_id: "a" }), run({ message_id: "b", created_at: "2026-11-03T11:00:00Z", optimized: true, inputs: optInputs })];
    const p = pendingOptimizedRun(runs, null);
    expect(p?.message_id).toBe("b");
    expect(pendingOptimizedRun(runs, { marker: runMarker(p!), original: geo, optimized: optInputs, view: "optimized" })).toBeNull();
    // a later plain frame run wins over the optimization
    expect(pendingOptimizedRun([...runs, run({ message_id: "c", created_at: "2026-11-03T12:00:00Z" })], null)).toBeNull();
  });

  it("maps optimized_frame3d from the chat optimization result", () => {
    const m = mapOptimizationFull({ kind: "optimization_full", status: "done", result: { groups: [] },
      optimized_frame3d: { inputs: optInputs }, original_inputs: geo });
    expect(m?.optimizedFrame).toEqual({ inputs: optInputs });
    expect(m?.originalInputs).toEqual(geo);
  });
});
