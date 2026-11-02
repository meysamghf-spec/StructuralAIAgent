import { afterEach, describe, expect, it, vi } from "vitest";

import { analyzeImport, fmt, ImportApiError, isCatalogName, parseImport, precheckFile, sectionEditFromMm } from "@/lib/model-import";

afterEach(() => vi.unstubAllGlobals());

describe("model import client", () => {
  it("rejects dwg with Save-As-DXF advice and accepts every CSI/DXF format", () => {
    expect(precheckFile("a.DWG")?.en).toMatch(/Save As/);
    expect(precheckFile("a.dwg")?.fa).toMatch(/DXF/);
    for (const n of ["b.s2k", "c.F2K", "plan.dxf"]) expect(precheckFile(n)).toBeNull();
    expect(isCatalogName("IPE300")).toBe(true);
    expect(isCatalogName("HE200B")).toBe(true);
    expect(isCatalogName("C50")).toBe(false);
    expect(precheckFile("c.txt")).not.toBeNull();
    expect(precheckFile("tower.e2k")).toBeNull();
  });
  it("converts mm section edits and formats numbers", () => {
    expect(sectionEditFromMm(300, 500)).toEqual({ b: 0.3, h: 0.5 });
    expect(sectionEditFromMm(0, 500)).toBeNull();
    expect(fmt(1e-14)).toBe("0");
    expect(fmt(4438.6)).toBe("4,439");
  });
  it("posts the file to /model-import/parse with the project id", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ stage: "review" }), { status: 200 }));
    vi.stubGlobal("fetch", f);
    await parseImport(new File(["$ STORIES"], "m.e2k"), "p1");
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/model-import\/parse$/);
    expect((init.body as FormData).get("project_id")).toBe("p1");
  });
  it("surfaces the bilingual 409 gate message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: { en: "Confirm every item", fa: "تأیید" } }), { status: 409 })));
    const err = await analyzeImport({}, null).catch((e) => e);
    expect(err).toBeInstanceOf(ImportApiError);
    expect(err.status).toBe(409);
    expect(err.fa).toBe("تأیید");
  });
});
