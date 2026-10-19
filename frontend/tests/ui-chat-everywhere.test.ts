import { describe, expect, it } from "vitest";
import { DEFAULT_FRAME_INPUTS, FRAME_FORM_FIELDS, formToInputs, inputsToForm } from "@/lib/frame3d-store";
import { NAV_ITEMS, visibleNavItems } from "@/lib/nav";
import { projectChatHref } from "@/lib/current-project";
import { makeUiT } from "@/lib/ui-i18n";

describe("manual frame form", () => {
  it("round-trips defaults and types numbers", () => {
    const form = inputsToForm(DEFAULT_FRAME_INPUTS);
    expect(form.storeys).toBe("3");
    const inputs = formToInputs({ ...form, storeys: "4.0", bay_x_m: "6,5", seismic_c: "" }, "fa");
    expect(inputs.storeys).toBe(4);
    expect(inputs.bay_x_m).toBe(6.5);
    expect(inputs.lang).toBe("fa");
    expect(inputs.foundation).toBe(true);
    expect("seismic_c" in inputs).toBe(false);
    expect(FRAME_FORM_FIELDS.every((f) => f.key in DEFAULT_FRAME_INPUTS)).toBe(true);
  });
  it("drops blank values so backend defaults apply", () => {
    const inputs = formToInputs({ storeys: "", zone: "" }, "en");
    expect(inputs.storeys).toBeUndefined();
    expect(inputs.zone).toBeUndefined();
  });
});

describe("navigation and project chat", () => {
  it("hides stub pages unless the flag is set", () => {
    const shown = visibleNavItems(false).map((i) => i.href);
    expect(shown).toContain("/workspace/model");
    expect(shown).not.toContain("/workspace/optimization");
    expect(visibleNavItems(true)).toHaveLength(NAV_ITEMS.length);
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
