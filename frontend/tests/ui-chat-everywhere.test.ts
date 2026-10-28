import { describe, expect, it } from "vitest";
import { DEFAULT_FRAME_INPUTS, FRAME_FORM_FIELDS, formToInputs, inputsToForm } from "@/lib/frame3d-store";
import { NAV_ITEMS, visibleNavItems } from "@/lib/nav";
import { projectChatHref } from "@/lib/current-project";
import { makeUiT } from "@/lib/ui-i18n";

describe("manual frame form", () => {
  it("round-trips defaults and types numbers", () => {
    // Geometry (storeys, bays, spans) has no default: it must be provided by the user.
    for (const k of ["storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m"]) expect(k in DEFAULT_FRAME_INPUTS).toBe(false);
    expect(inputsToForm(DEFAULT_FRAME_INPUTS).storeys).toBe("");
    const form = inputsToForm({ ...DEFAULT_FRAME_INPUTS, storeys: 3, bays_x: 2, bays_y: 2, bay_x_m: 5, bay_y_m: 5 });
    expect(form.storeys).toBe("3");
    const inputs = formToInputs({ ...form, storeys: "4.0", bay_x_m: "6,5", seismic_c: "" }, "fa");
    expect(inputs.storeys).toBe(4);
    expect(inputs.bay_x_m).toBe(6.5);
    expect(inputs.lang).toBe("fa");
    expect(inputs.foundation).toBe(true);
    expect("seismic_c" in inputs).toBe(false);
    const geometry = new Set(["storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m"]);
    expect(FRAME_FORM_FIELDS.every((f) => geometry.has(f.key) || f.key in DEFAULT_FRAME_INPUTS)).toBe(true);
    // a typed span in cm/ft converts to metres
    expect(formToInputs({ bay_x_m: "600" }, "en", { bay_x_m: "cm" }).bay_x_m).toBe(6);
  });
  it("drops blank values so backend defaults apply", () => {
    const inputs = formToInputs({ storeys: "", zone: "" }, "en");
    expect(inputs.storeys).toBeUndefined();
    expect(inputs.zone).toBeUndefined();
  });
});

describe("navigation and project chat", () => {
  it("lists every page (no hidden pages, no env flag)", () => {
    const shown = visibleNavItems().map((i) => i.href);
    expect(shown).toContain("/workspace/model");
    expect(shown).toContain("/workspace/optimization");
    expect(visibleNavItems()).toHaveLength(NAV_ITEMS.length);
  });
  it("builds project chat links and translates the shell", () => {
    expect(projectChatHref("a b")).toBe("/?project=a%20b");
    const fa = makeUiT("fa");
    expect(fa("Projects")).toBe("پروژه‌ها");
    expect(fa("PASS")).toBe("قبول");
    expect(makeUiT("en")("Projects")).toBe("Projects");
    expect(NAV_ITEMS.every((i) => fa(i.label) !== i.label)).toBe(true);
  });
});
