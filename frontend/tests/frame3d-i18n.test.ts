import { describe, expect, it } from "vitest";
import { FA_DICTIONARY, isRtl, makeT, normalizeLang } from "@/lib/frame3d-i18n";
import { mapFrame3dFoundation } from "@/lib/chat-mappers";
import { foundationRows } from "@/components/chat/Frame3dResultCard";

describe("frame3d i18n", () => {
  it("translates in fa and passes through in en", () => {
    const fa = makeT("fa");
    const en = makeT("en");
    expect(fa("PASS")).toBe("قبول");
    expect(fa("Storey drift")).toBe("دریفت طبقات");
    expect(fa("unknown key")).toBe("unknown key");
    expect(en("PASS")).toBe("PASS");
    expect(isRtl("fa")).toBe(true);
    expect(isRtl("en")).toBe(false);
    expect(normalizeLang("fa")).toBe("fa");
    expect(normalizeLang("x")).toBe("en");
    expect(Object.values(FA_DICTIONARY).every((v) => v.length > 0)).toBe(true);
  });

  it("maps foundation payload and builds size column", () => {
    const f = mapFrame3dFoundation({
      status: "PASS",
      qa_kpa: 150,
      qa_assumed: true,
      qa_net_kpa: 130,
      rows: [{ group: "F-corner", B_m: 1.9, h_m: 0.3, bars: "Φ14@250" }],
      overlap: { min_gap_m: 2.45, coverage_ratio: 0.3, recommendation: "ok" },
      clauses_implemented: ["a"],
      clauses_simplified: [],
    });
    expect(f?.qaAssumed).toBe(true);
    expect(f?.minGapM).toBe(2.45);
    expect(foundationRows(f!.rows)[0].size).toBe("1.9 × 1.9 × 0.3");
    expect(mapFrame3dFoundation(null)).toBeNull();
  });
});
