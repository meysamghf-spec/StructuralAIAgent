import { describe, expect, it } from "vitest";

import {
  formatCryptoAmount,
  formatFiatAmount,
  getPaymentProgressMessage,
  getPaymentStatusLabel,
} from "../lib/upgrades-workspace";

describe("upgrades workspace helpers", () => {
  it("formats payment status labels", () => {
    expect(getPaymentStatusLabel("AWAITING_PAYMENT")).toBe("AWAITING PAYMENT");
  });

  it("formats fiat and crypto amounts", () => {
    expect(formatFiatAmount(49)).toBe("$49.00 USD");
    expect(formatCryptoAmount(0.00098, "BTC")).toContain("BTC");
  });

  it("describes payment progress by status", () => {
    expect(getPaymentProgressMessage("PAID", 3, 3)).toContain("active");
    expect(getPaymentProgressMessage("CONFIRMING", 1, 3)).toContain("Confirming");
  });
});
