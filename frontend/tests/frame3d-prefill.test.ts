import { describe, expect, it } from "vitest";

import { prefillGeometry } from "@/lib/frame3d-prefill";

describe("prefillGeometry", () => {
  it("fills blanks from the chat, then defaults; keeps typed values", () => {
    const r = prefillGeometry(
      { storeys: "13", bays_x: "", bays_y: "", bay_x_m: "", bay_y_m: "" },
      { inputs: { storeys: 6, bays_x: 2, bays_y: 4, bay_x_m: 6, bay_y_m: null }, from_chat: ["storeys", "bays_x", "bays_y", "bay_x_m"] },
    );
    expect(r.values).toMatchObject({ storeys: "13", bays_x: "2", bays_y: "4", bay_x_m: "6", bay_y_m: "5" });
    expect(r.fromChat).toEqual(["bays_x", "bays_y", "bay_x_m"]);
    expect(r.assumed).toEqual(["bay_y_m"]);
  });

  it("no chat frame → all defaults, nothing left blank", () => {
    const r = prefillGeometry({}, null);
    expect(r.values).toMatchObject({ storeys: "4", bays_x: "3", bays_y: "3", bay_x_m: "5", bay_y_m: "5" });
    expect(r.assumed).toHaveLength(5);
  });
});

import { FRAME_LIMITS, validateGeometry } from "@/components/frame3d/GeometryField";

describe("validateGeometry limits", () => {
  const base = { storeys: "3", bays_x: "2", bays_y: "2", bay_x_m: "5", bay_y_m: "5" };
  const keys = ["storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m"];
  it("states the max for bays and storeys", () => {
    const e = validateGeometry({ ...base, bays_y: "200", bays_x: "100" }, {}, "en", keys);
    expect(e.bays_y).toContain(`max allowed ${FRAME_LIMITS.bays}`);
    expect(e.bays_x).toContain(`max allowed ${FRAME_LIMITS.bays}`);
    expect(validateGeometry({ ...base, storeys: "130" }, {}, "fa", keys).storeys).toContain("حداکثر");
    expect(validateGeometry({ ...base, storeys: "13" }, {}, "fa", keys).storeys).toBeUndefined();
  });
  it("checks the solver node limit", () => {
    const e = validateGeometry({ ...base, storeys: "50", bays_x: "20", bays_y: "20" }, {}, "en", keys);
    expect(e.bays_x).toContain(`max ${FRAME_LIMITS.nodes}`);
    // ETABS-scale models within the cap are accepted (e.g. 30 storeys, 15×15 bays = 7 936 nodes)
    expect(validateGeometry({ ...base, storeys: "30", bays_x: "15", bays_y: "15" }, {}, "en", keys)).toEqual({});
    expect(validateGeometry(base, {}, "en", keys)).toEqual({});
  });
});

describe("prefill of non-geometry values from the project's chats", () => {
  it("replaces generic defaults with chat values but keeps saved ones", () => {
    const vals = { storeys: "", bays_x: "", bays_y: "", bay_x_m: "", bay_y_m: "", storey_height_m: "3.2", dead_kn_m2: "6", live_kn_m2: "2" };
    const chat = { inputs: { storeys: 5, bays_x: 3, bays_y: 3, bay_x_m: 6, bay_y_m: 6, storey_height_m: 3.5, dead_kn_m2: 7, live_kn_m2: 2.5 },
      from_chat: ["storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m", "storey_height_m", "dead_kn_m2", "live_kn_m2"] };
    const r = prefillGeometry(vals, chat, new Set(["live_kn_m2"]));
    expect(r.values.storey_height_m).toBe("3.5");
    expect(r.values.dead_kn_m2).toBe("7");
    expect(r.values.live_kn_m2).toBe("2");
    expect(r.assumed).toEqual([]);
  });
});
