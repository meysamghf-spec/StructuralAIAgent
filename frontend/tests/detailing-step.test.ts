import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DETAILING_COMMAND,
  DETAILING_ITEMS,
  detailingDoneAt,
  detailingFromGlance,
  detailingStatus,
  detailingStatusLabel,
  markDetailingDone,
} from "@/lib/detailing-step";
import { download, DOWNLOADS } from "@/lib/frame3d-downloads";
import { loadDetailingPlan, resetDetailingPlanCache } from "@/lib/detailing-plan";

const src = (p: string) => readFileSync(path.resolve(__dirname, "..", p), "utf8");

function fakeStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
  };
}

describe("detailing status (honest, derived)", () => {
  it("is not run without a design, ready with one, done only after output was generated", () => {
    expect(detailingStatus({ hasDesign: false })).toBe("not_run");
    expect(detailingStatus({ hasDesign: false, doneAt: "2026-01-01T00:00:00Z" })).toBe("not_run");
    expect(detailingStatus({ hasDesign: true })).toBe("ready");
    expect(detailingStatus({ hasDesign: true, doneAt: "2026-01-01T00:00:00Z" })).toBe("done");
  });

  it("respects the plan gate (rebar_sheets) unless enforcement is off", () => {
    const free = ["mabhas9_check"];
    expect(detailingStatus({ hasDesign: true, designSheets: free, enforcement: true })).toBe("locked");
    expect(detailingStatus({ hasDesign: true, designSheets: free, enforcement: false })).toBe("ready");
    expect(detailingStatus({ hasDesign: true, designSheets: [...free, "rebar_sheets"], enforcement: true })).toBe("ready");
    expect(detailingStatus({ hasDesign: true, designSheets: null })).toBe("ready");
    expect(detailingStatus({ hasDesign: false, designSheets: free, enforcement: true })).toBe("not_run");
  });

  it("has English and Persian labels for every status", () => {
    for (const s of ["not_run", "ready", "done", "locked"] as const) {
      expect(detailingStatusLabel(s, "en")).toBeTruthy();
      expect(/[\u0600-\u06ff]/.test(detailingStatusLabel(s, "fa"))).toBe(true);
    }
    expect(/[\u0600-\u06ff]/.test(DETAILING_COMMAND.fa)).toBe(true);
    expect(DETAILING_COMMAND.en).toBe("detail the rebar");
  });

  it("maps the Assistants glance value", () => {
    expect(detailingFromGlance("Available")).toBe("done");
    expect(detailingFromGlance("Ready")).toBe("ready");
    expect(detailingFromGlance("Not run")).toBe("not_run");
    expect(detailingFromGlance(undefined)).toBe("not_run");
  });
});

describe("detailing wiring to the real outputs", () => {
  it("only counts outputs that exist in the downloads registry", () => {
    const drawings = DOWNLOADS.drawings.map((d) => d.name);
    for (const n of DETAILING_ITEMS) expect(drawings).toContain(n);
  });
});

describe("done marker", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", fakeStorage());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("is stored per project", () => {
    expect(detailingDoneAt("p1")).toBeNull();
    markDetailingDone("p1", new Date("2026-02-03T04:05:06Z"));
    expect(detailingDoneAt("p1")).toBe("2026-02-03T04:05:06.000Z");
    expect(detailingDoneAt("p2")).toBeNull();
    expect(detailingDoneAt(null)).toBeNull();
  });

  it("is set by a real rebar download but not by other downloads or failed ones", async () => {
    vi.stubGlobal("document", { createElement: () => ({ click() {} , remove() {} }), body: { appendChild() {} } });
    vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL() {} });
    const ok = () => new Response("0\nEOF", { status: 200, headers: { "content-disposition": 'attachment; filename="rebar.dxf"' } });
    vi.stubGlobal("fetch", vi.fn(async () => ok()));
    await download({ kind: "drawing", name: "dxf_plans" }, "dxf", { inputs: {}, projectId: "p1" });
    expect(detailingDoneAt("p1")).toBeNull();
    await download({ kind: "table", name: "dxf_rebar" }, "dxf", { inputs: {}, projectId: "p1" });
    expect(detailingDoneAt("p1")).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "plan" }), { status: 402 })));
    await expect(download({ kind: "drawing", name: "dxf_rebar" }, "dxf", { inputs: {}, projectId: "p1" })).rejects.toThrow("plan");
    expect(detailingDoneAt("p1")).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => ok()));
    await download({ kind: "drawing", name: "dxf_rebar" }, "dxf", { inputs: {}, projectId: "p1" });
    expect(detailingDoneAt("p1")).not.toBeNull();
  });
});

describe("plan lookup", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetDetailingPlanCache();
  });
  it("falls back to unrestricted view when the account cannot be read (backend still enforces)", async () => {
    resetDetailingPlanCache();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 401 })));
    expect(await loadDetailingPlan()).toEqual({ designSheets: null, enforcement: false });
  });
});

describe("placement: Detailing comes right after Design", () => {
  it("result card renders Detailing between Design and Foundation", () => {
    const s = src("components/chat/Frame3dResultCard.tsx");
    const d = s.indexOf("<DesignSection design=");
    const x = s.indexOf("<DetailingStep");
    const f = s.indexOf("<FoundationSection foundation=");
    expect(d).toBeGreaterThan(0);
    expect(x).toBeGreaterThan(d);
    expect(f).toBeGreaterThan(x);
  });
  it("Assistants stepper lists Detailing after Design and before Output", () => {
    const s = src("app/workspace/agents/AgentsWorkspaceClient.tsx");
    const a = s.indexOf('["Design", workflowGlance?.design]');
    const b = s.indexOf('["Detailing", workflowGlance?.detailing]');
    const c = s.indexOf('["Output", workflowGlance?.output]');
    expect(a).toBeGreaterThan(0);
    expect(b).toBeGreaterThan(a);
    expect(c).toBeGreaterThan(b);
    expect(s).toContain('["Detailing", workflowGlance?.detailing ?? "Not run"]');
  });
  it("stepper grid has five columns and the dossier mentions Detailing", () => {
    expect(src("app/globals.css")).toMatch(/\.workflow-steps \{[^}]*repeat\(5, minmax\(0, 1fr\)\)/);
    expect(src("components/agents/RunDossier.tsx")).toMatch(/Design \{workflow\.design\} · Detailing \{workflow\.detailing\}/);
  });
  it("chat card is RTL-aware and mobile-safe", () => {
    const c = src("components/frame3d/DetailingStep.tsx");
    expect(c).toContain('dir={rtl ? "rtl" : "ltr"}');
    const css = src("app/globals.css");
    expect(css).toContain(".detailing-step-actions .button { min-width: 0; max-width: 100%");
    expect(css).toContain("border-inline-start");
  });
});
