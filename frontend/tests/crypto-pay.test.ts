import { describe, expect, it } from "vitest";

import type { CryptoAsset, Invoice } from "../lib/billing";
import { countdownLabel, defaultAsset, displayAmount, isTxHash, payStage, payT, PAY_FA, selectableAssets, txUrl } from "../lib/crypto-pay";

const asset = (o: Partial<CryptoAsset>): CryptoAsset => ({
  id: "x", coin: "USDT", network: "N", standard: "BEP20", stable: true, optional: false, live: false, contract: "", processor: "p", ...o,
});
const inv = (o: Partial<Invoice>): Invoice =>
  ({ id: "i", status: "pending", mock: false, expires_at: new Date(Date.now() + 60_000).toISOString(), ...o }) as Invoice;

describe("crypto pay helpers", () => {
  it("prefers live USDT BEP20 and hides unavailable assets", () => {
    const list = [
      asset({ id: "usdt-trc20", available: false }),
      asset({ id: "usdt-bep20", live: true, available: true }),
      asset({ id: "eth", coin: "ETH", available: true }),
    ];
    expect(selectableAssets(list).map((a) => a.id)).toEqual(["usdt-bep20", "eth"]);
    expect(defaultAsset(list)?.id).toBe("usdt-bep20");
    expect(defaultAsset([asset({ id: "a", available: false })])).toBeUndefined();
  });

  it("derives the payment stage", () => {
    const now = Date.now();
    expect(payStage(inv({}), now)).toBe("awaiting");
    expect(payStage(inv({ expires_at: new Date(now - 1).toISOString() }), now)).toBe("window_ended");
    expect(payStage(inv({ detected: { tx: "0x", block: 1, confirmations: 3, required: 30 } }), now)).toBe("confirming");
    expect(payStage(inv({ underpaid: { tx: "0x", received: "1", missing: "2" } }), now)).toBe("underpaid");
    expect(payStage(inv({ status: "paid" }), now)).toBe("paid");
    expect(payStage(inv({ status: "expired" }), now)).toBe("closed");
  });

  it("formats countdown and validates tx hashes / links", () => {
    const now = Date.now();
    expect(countdownLabel(new Date(now + 125_000).toISOString(), now)).toBe("2:05");
    expect(countdownLabel(new Date(now - 5).toISOString(), now)).toBe("0:00");
    const h = "0x" + "ab".repeat(32);
    expect(isTxHash(h)).toBe(true);
    expect(isTxHash("0x12")).toBe(false);
    expect(txUrl(inv({ explorer: "https://bscscan.com" }), h)).toBe(`https://bscscan.com/tx/${h}`);
    expect(txUrl(inv({}), h)).toBe("");
  });

  it("pads stable amounts to 3 decimals", () => {
    expect(displayAmount("15.86", true)).toBe("15.860");
    expect(displayAmount("15", true)).toBe("15.000");
    expect(displayAmount("0.0123", false)).toBe("0.0123");
  });

  it("translates with variables and falls back to English", () => {
    expect(payT("en", "Payment detected: {n} of {total} network confirmations. Your plan activates automatically.", { n: 3, total: 30 })).toContain("3 of 30");
    const k = "Payment detected: {n} of {total} network confirmations. Your plan activates automatically.";
    expect(payT("fa", k, { n: 3, total: 30 })).toContain("3 از 30");
    expect(payT("fa", "unknown key")).toBe("unknown key");
  });

  it("has a Persian string for every pay-page key used by the warning", () => {
    for (const k of ["Pay with crypto", "Amount", "Address", "Copy", "Verify transaction", "Back to plans"]) expect(PAY_FA[k]).toBeTruthy();
  });
});
