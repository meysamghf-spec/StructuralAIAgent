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
