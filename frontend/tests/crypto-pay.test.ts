import { describe, expect, it } from "vitest";

import type { CryptoAsset, Invoice } from "../lib/billing";
import { chainKey, confirmEta, countdownLabel, defaultAsset, displayAmount, etaText, explorerLabel, isAutoDetected, isHighFeeChain, isTxHash, networkNote, payStage, payT, PAY_FA, selectableAssets, tokenUrl, txUrl } from "../lib/crypto-pay";

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

  it("has a per-network warning; Ethereum warns about high gas fees in both languages", () => {
    expect(networkNote(1)).toMatch(/fees \(gas\) are high/);
    expect(networkNote(137)).toMatch(/USDC\.e/);
    expect(networkNote(137)).toMatch(/USDT0/);
    expect(networkNote(56)).toMatch(/BEP20/);
    expect(networkNote(null)).toBe("");
    expect(isHighFeeChain(1)).toBe(true);
    expect(isHighFeeChain(56)).toBe(false);
    for (const id of [1, 56, 137]) {
      const fa = payT("fa", networkNote(id));
      expect(fa).not.toBe(networkNote(id)); // translated
      expect(/[\u0600-\u06FF]/.test(fa)).toBe(true);
    }
    expect(payT("fa", networkNote(1))).toMatch(/گس|کارمزد/);
  });

  it("names the right block explorer and estimates confirmation time per chain", () => {
    expect(explorerLabel(1)).toBe("Verify on Etherscan");
    expect(explorerLabel(137)).toBe("Verify on PolygonScan");
    expect(explorerLabel(56)).toBe("Verify on BscScan");
    for (const k of ["Verify on Etherscan", "Verify on PolygonScan", "Verify on BscScan"]) expect(PAY_FA[k]).toBeTruthy();
    expect(confirmEta(56, 30).seconds).toBeLessThan(30);
    expect(confirmEta(137, 64).seconds).toBeGreaterThan(100);
    expect(confirmEta(1, 12).seconds).toBe(144);
    expect(etaText("en", 14)).toBe("14 seconds");
    expect(etaText("en", 144)).toBe("2 minutes");
    expect(etaText("fa", 144)).toBe("2 دقیقه");
  });

  it("the generic warning no longer calls ERC20 an unsupported network", () => {
    const k = Object.keys(PAY_FA).find((x) => x.startsWith("Send only {coin} on {network}"))!;
    expect(k).not.toMatch(/ERC20/);
    expect(payT("en", k, { coin: "USDC", network: "Polygon (PoS)" })).toContain("Send only USDC on Polygon (PoS)");
  });

  it("default asset stays USDT BEP20 with six live options", () => {
    const six = ["usdt-bep20", "usdc-bep20", "usdt-polygon", "usdc-polygon", "usdt-erc20", "usdc-erc20"].map((id) =>
      asset({ id, coin: id.startsWith("usdt") ? "USDT" : "USDC", live: true, available: true }),
    );
    const list = [asset({ id: "btc-onchain", coin: "BTC", available: false }), ...six.reverse()];
    expect(selectableAssets(list)).toHaveLength(6);
    expect(defaultAsset(list)?.id).toBe("usdt-bep20");
  });

  it("default asset stays USDT BEP20 with all eight live options", () => {
    const ids = ["usdt-bep20", "usdc-bep20", "usdt-polygon", "usdc-polygon", "usdt-erc20", "usdc-erc20", "usdt-trc20", "btc-onchain"];
    const list = [...ids].reverse().map((id) => asset({ id, coin: id.startsWith("usdt") ? "USDT" : id.startsWith("usdc") ? "USDC" : "BTC", live: true, available: true }));
    list.push(asset({ id: "btc-lightning", coin: "BTC", available: false }), asset({ id: "ltc", coin: "LTC", available: false }), asset({ id: "ton", coin: "TON", available: false }));
    expect(selectableAssets(list)).toHaveLength(8);
    expect(defaultAsset(list)?.id).toBe("usdt-bep20");
  });

  it("maps EVM chain ids and chain names to the same keys", () => {
    expect([chainKey(56), chainKey(1), chainKey(137), chainKey("tron"), chainKey("btc"), chainKey(null), chainKey(999)]).toEqual(["bsc", "eth", "polygon", "tron", "btc", "", ""]);
    expect(networkNote("eth")).toBe(networkNote(1));
    expect(isHighFeeChain("eth")).toBe(true);
    expect(isHighFeeChain("tron")).toBe(false);
  });

  it("has Tron and Bitcoin warnings in both languages, and the Bitcoin one fills in the confirmations", () => {
    expect(networkNote("tron")).toMatch(/TRX/);
    expect(networkNote("btc")).toMatch(/ONE on-chain transaction/);
    expect(networkNote("btc")).toMatch(/Lightning is not supported/);
    for (const c of ["tron", "btc"]) {
      const fa = payT("fa", networkNote(c), { n: 3 });
      expect(/[\u0600-\u06FF]/.test(fa)).toBe(true);
      expect(fa).not.toContain("{n}");
    }
    expect(payT("en", networkNote("btc"), { n: 3 })).toContain("Bitcoin needs 3 confirmations");
    expect(PAY_FA["Bitcoin (on-chain)"]).toBeTruthy();
    expect(PAY_FA["Coin"]).toBeTruthy();
  });

  it("labels explorers and estimates times for Tron and Bitcoin", () => {
    expect(explorerLabel("tron")).toBe("Verify on Tronscan");
    expect(explorerLabel("btc")).toBe("Verify on mempool.space");
    for (const k of ["Verify on Tronscan", "Verify on mempool.space"]) expect(PAY_FA[k]).toBeTruthy();
    expect(confirmEta("tron", 20).seconds).toBe(60);
    expect(confirmEta("btc", 3).seconds).toBe(1800);
    expect(etaText("en", 1800)).toBe("30 minutes");
  });

  it("builds explorer links per chain and accepts bare 64-hex ids for Tron and Bitcoin", () => {
    const bare = "cd".repeat(32);
    const evm = "0x" + bare;
    expect(isTxHash(bare)).toBe(true);
    expect(isTxHash(evm)).toBe(true);
    expect(isTxHash("cd".repeat(31))).toBe(false);
    expect(isTxHash("zz".repeat(32))).toBe(false);
    expect(txUrl(inv({ chain: "tron", explorer: "https://tronscan.org/#" }), bare)).toBe(`https://tronscan.org/#/transaction/${bare}`);
    expect(txUrl(inv({ chain: "tron", explorer: "https://tronscan.org/#" }), evm)).toBe(`https://tronscan.org/#/transaction/${bare}`);
    expect(txUrl(inv({ chain: "btc", explorer: "https://mempool.space" }), bare)).toBe(`https://mempool.space/tx/${bare}`);
    expect(txUrl(inv({ chain: "btc", explorer: "https://mempool.space" }), evm)).toBe("");
    expect(txUrl(inv({ chain: "bsc", explorer: "https://bscscan.com" }), bare)).toBe("");
    expect(tokenUrl(inv({ chain: "tron", explorer: "https://tronscan.org/#", contract: "TR7N" }))).toBe("https://tronscan.org/#/token20/TR7N");
    expect(tokenUrl(inv({ chain: "bsc", explorer: "https://bscscan.com", contract: "0xabc" }))).toBe("https://bscscan.com/token/0xabc");
    expect(tokenUrl(inv({ chain: "btc", explorer: "https://mempool.space" }))).toBe("");
  });

  it("auto-detect applies to every live chain but never to test invoices", () => {
    expect(isAutoDetected(inv({ auto_detect: true, chain: "btc" }))).toBe(true);
    expect(isAutoDetected(inv({ auto_detect: true, mock: true }))).toBe(false);
    expect(isAutoDetected(inv({ contract: "0x1", chain_id: 56 }))).toBe(true);
    expect(isAutoDetected(inv({}))).toBe(false);
  });
});
