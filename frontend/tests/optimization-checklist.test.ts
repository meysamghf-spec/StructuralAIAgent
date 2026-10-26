import { describe, expect, it } from "vitest";

import { incompleteInputs, isIncompleteFramePayload } from "@/components/frame3d/Frame3dWorkspacePanel";
import {
  autoCompleteHref,
  chatHrefForCommand,
  isChecklist,
  stepActionLang,
  type OptimizationChecklist,
} from "@/lib/optimization-checklist";

const checklist: OptimizationChecklist = {
  ready: false,
  missing_keys: ["model", "analysis"],
  steps: [
    {
      key: "model", done: false, optional: false,
      label: { en: "Structural model defined", fa: "مدل سازه تعریف شده" },
      detail: { en: "The model has no members yet.", fa: "هنوز هیچ عضوی نیست." },
      action: { kind: "chat", label: { en: "Describe the frame", fa: "توصیف قاب" }, command: "optimize a 3-storey frame" },
    },
    {
      key: "analysis", done: false, optional: false,
      label: { en: "Analysis run completed", fa: "تحلیل انجام شده" },
      detail: { en: "0 usable", fa: "۰" },
      action: { kind: "link", label: { en: "Run analysis", fa: "اجرای تحلیل" }, href: "/workspace/analysis?project=p1" },
    },
    { key: "design", done: true, optional: true, label: { en: "d", fa: "d" }, detail: { en: "", fa: "" }, action: null },
  ],
  auto_complete: { available: true, assumptions: { en: ["a"], fa: ["ب"] }, command: { en: "assume defaults", fa: "پیش‌فرض‌ها را فرض کن" } },
};

describe("optimization checklist helpers", () => {
  it("recognises a checklist payload", () => {
    expect(isChecklist(checklist)).toBe(true);
    expect(isChecklist({})).toBe(false);
    expect(isChecklist(null)).toBe(false);
  });

  it("turns chat steps into a prefilled chat link and link steps into their href", () => {
    const chat = stepActionLang(checklist.steps[0], "fa", "p1");
    expect(chat?.label).toBe("توصیف قاب");
    expect(chat?.href).toContain("prompt=optimize+a+3-storey+frame");
    expect(chat?.href).toContain("project=p1");
    expect(stepActionLang(checklist.steps[1], "en", "p1")?.href).toBe("/workspace/analysis?project=p1");
    expect(stepActionLang(checklist.steps[2], "en", "p1")).toBeNull();
  });

  it("auto-complete link carries the assume-defaults command in the chosen language", () => {
    expect(decodeURIComponent(autoCompleteHref(checklist, "en", "p1").replace(/\+/g, " "))).toContain("assume defaults");
    expect(chatHrefForCommand("x", null)).toBe("/?prompt=x");
  });

  it("detects an incomplete stored frame run and exposes its inputs for repair", () => {
    const old = { status: "MISSING_REQUIRED_INPUT", missing_inputs: ["bays_x"], inputs: { storeys: 3, bays_x: null } };
    expect(isIncompleteFramePayload(old)).toBe(true);
    expect(incompleteInputs(old)).toEqual({ storeys: 3, bays_x: null });
    expect(isIncompleteFramePayload({ status: "completed" })).toBe(false);
    expect(isIncompleteFramePayload({ status: "MISSING_REQUIRED_INPUT", missing_inputs: ["frame_model"] })).toBe(false);
  });
});
