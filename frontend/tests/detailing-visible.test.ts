import { describe, expect, it } from "vitest";

import { NAV_ITEMS, titleForPath } from "@/lib/nav";
import { UI_FA } from "@/lib/ui-i18n";

describe("Detailing is a visible menu page", () => {
  it("is listed right after Design and titled", () => {
    const i = NAV_ITEMS.findIndex((n) => n.href === "/workspace/detailing");
    expect(i).toBeGreaterThan(0);
    expect(NAV_ITEMS[i - 1].href).toBe("/workspace/design");
    expect(titleForPath("/workspace/detailing")).toBe("Detailing");
    expect(UI_FA.Detailing).toBeTruthy();
  });
});
