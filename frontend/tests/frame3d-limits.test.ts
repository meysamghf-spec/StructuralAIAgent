import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { FRAME_LIMITS, frameNodeCount } from "@/lib/frame3d-limits";

// The backend module is the single source of truth; the frontend mirror must match it exactly.
const py = readFileSync(resolve(__dirname, "../../backend/app/application/frame3d_limits.py"), "utf8");
const val = (name: string) => Number(new RegExp(`^${name}\\s*=\\s*([0-9.]+)`, "m").exec(py)?.[1]);

describe("frame3d limits stay in sync with the backend", () => {
  it("matches backend/app/application/frame3d_limits.py", () => {
    expect(FRAME_LIMITS.storeys).toBe(val("MAX_STOREYS"));
    expect(FRAME_LIMITS.bays).toBe(val("MAX_BAYS"));
    expect(FRAME_LIMITS.nodes).toBe(val("MAX_NODES"));
    expect(FRAME_LIMITS.optNodes).toBe(val("MAX_OPT_NODES"));
    expect(FRAME_LIMITS.backgroundNodes).toBe(val("BACKGROUND_NODES"));
    expect(FRAME_LIMITS.minSpanM).toBe(val("MIN_SPAN_M"));
    expect(FRAME_LIMITS.maxSpanM).toBe(val("MAX_SPAN_M"));
  });
  it("counts nodes like the solver", () => {
    expect(frameNodeCount(30, 15, 15)).toBe(7936);
  });
});
