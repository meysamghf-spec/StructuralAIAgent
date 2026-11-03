// Pure helpers + Persian/English strings for the crypto payment page (kept free of React so they can be unit-tested).
import type { CryptoAsset, Invoice } from "./billing";

export type PayLang = "en" | "fa";

export const PAY_FA: Record<string, string> = {
  "← Plans": "← طرح‌ها",
  "Pay with crypto": "پرداخت با ارز دیجیتال",
  "month": "ماه",
  "months": "ماه",
  "(reference)": "(مرجع)",
  "1. Coin": "۱. ارز",
  "2. Network": "۲. شبکه",
  "Processed by": "روش پردازش",
  "Create payment": "ایجاد پرداخت",
  "Creating…": "در حال ایجاد…",
  "No payment method is available right now. Please try again later.": "در حال حاضر روش پرداختی فعال نیست. لطفاً بعداً تلاش کنید.",
  "Invoice": "فاکتور",
  "Test invoice: this wallet is not configured yet, so the address below is a placeholder. Do not send real coins. Use “Simulate payment”.":
    "فاکتور آزمایشی: کیف پول هنوز تنظیم نشده و آدرس زیر فقط نمونه است. ارز واقعی نفرستید. از «شبیه‌سازی پرداخت» استفاده کنید.",
  "Network": "شبکه",
  "Token": "توکن",
  "Coin": "ارز",
  "BNB Smart Chain (BEP20)": "بایننس اسمارت چین (BEP20)",
  "Ethereum (ERC20)": "اتریوم (ERC20)",
  "Polygon (PoS)": "پالیگان (PoS)",
  "Tron (TRC20)": "ترون (TRC20)",
  "Bitcoin (on-chain)": "بیت‌کوین (آن‌چین)",
  "Tron fees are paid in TRX (or energy) that must be in your wallet: without it the transfer fails. Send USDT on the Tron (TRC20) network only; do not use ERC20, BEP20 or Polygon for this address, those coins would be lost.":
    "کارمزد ترون با TRX (یا انرژی) پرداخت می‌شود که باید در کیف پول شما باشد؛ بدون آن انتقال ناموفق می‌شود. فقط USDT را روی شبکهٔ Tron (TRC20) بفرستید؛ برای این آدرس از ERC20، BEP20 یا Polygon استفاده نکنید، آن ارز از بین می‌رود.",
  "Send the exact BTC amount shown in ONE on-chain transaction, with the network fee paid on top (do not choose “subtract fee from amount”). Lightning is not supported. The amount is fixed at the price when you created this payment; the last digits identify your invoice. Bitcoin needs {n} confirmations, usually about 30 minutes or more.":
    "دقیقاً همان مقدار BTC نمایش‌داده‌شده را در یک تراکنش آن‌چین بفرستید و کارمزد شبکه را جدا و اضافه بپردازید (گزینهٔ «کسر کارمزد از مبلغ» را انتخاب نکنید). Lightning پشتیبانی نمی‌شود. مبلغ بر اساس قیمت لحظهٔ ساخت این پرداخت ثابت شده؛ رقم‌های آخر، فاکتور شما را مشخص می‌کنند. بیت‌کوین به {n} تأییدیه نیاز دارد، معمولاً حدود ۳۰ دقیقه یا بیشتر.",
  "Verify on Tronscan": "بررسی در Tronscan",
  "Verify on mempool.space": "بررسی در mempool.space",
  "Paste the transaction id (64 characters) and we will verify it on the blockchain.":
    "شناسهٔ تراکنش (۶۴ کاراکتر) را وارد کنید تا روی بلاک‌چین بررسی کنیم.",
  "Send only {coin} on {network}. Any other token or network will be lost and cannot be recovered. Send exactly the amount shown, including the last digits: they identify your invoice.":
    "فقط {coin} روی شبکهٔ {network} بفرستید. هر توکن یا شبکهٔ دیگر از بین می‌رود و قابل بازیابی نیست. دقیقاً همان مبلغ نمایش‌داده‌شده را با همهٔ ارقام اعشار بفرستید؛ رقم‌های آخر، فاکتور شما را مشخص می‌کنند.",
  "BEP20 is cheap: the network fee is a few cents, paid in a little BNB that must be in your wallet. Do not send from or to Ethereum, Polygon or Tron addresses: those coins would be lost.":
    "شبکهٔ BEP20 ارزان است: کارمزد شبکه چند سنت است و با کمی BNB که باید در کیف پول شما باشد پرداخت می‌شود. از/به آدرس‌های اتریوم، پالیگان یا ترون نفرستید؛ آن ارز از بین می‌رود.",
  "Polygon fees are very low, paid in a little POL that must be in your wallet. Send native Polygon PoS tokens only (for USDC: the native “USDC”, not the older bridged “USDC.e”). Some wallets show Polygon USDT as “USDT0”: it is the same Tether token, send it normally.":
    "کارمزد پالیگان بسیار کم است و با کمی POL که باید در کیف پول شما باشد پرداخت می‌شود. فقط توکن‌های اصلی شبکهٔ Polygon PoS را بفرستید (برای USDC: همان «USDC» اصلی، نه «USDC.e» قدیمی پل‌شده). بعضی کیف پول‌ها USDT پالیگان را «USDT0» نشان می‌دهند؛ همان توکن Tether است و عادی بفرستید.",
  "Ethereum network fees (gas) are high: often several dollars up to tens of dollars, paid in ETH that must be in your wallet, and they can be more than the cost of a small plan. If you can, choose BNB Smart Chain (BEP20) or Polygon, which cost cents. Confirmation takes a few minutes.":
    "کارمزد (گس) شبکهٔ اتریوم بالاست: اغلب چند دلار تا ده‌ها دلار، با ETH که باید در کیف پول شما باشد، و می‌تواند از هزینهٔ یک طرح کوچک بیشتر شود. اگر می‌توانید، BNB Smart Chain (BEP20) یا Polygon را انتخاب کنید که چند سنت هزینه دارد. تأیید چند دقیقه طول می‌کشد.",
  "Needs {n} network confirmations (about {time}).": "به {n} تأییدیهٔ شبکه نیاز دارد (حدود {time}).",
  "{n} seconds": "{n} ثانیه",
  "{n} minutes": "{n} دقیقه",
  "Verify on BscScan": "بررسی در BscScan",
  "Verify on Etherscan": "بررسی در Etherscan",
  "Verify on PolygonScan": "بررسی در PolygonScan",
  "Amount": "مبلغ",
  "Address": "آدرس",
  "Token contract": "قرارداد توکن",
  "Rate": "نرخ",
  "locked until expiry": "تا پایان مهلت ثابت است",
  "Copy": "کپی",
  "Copied": "کپی شد",
  "QR with amount": "QR همراه مبلغ",
  "QR address only": "QR فقط آدرس",
  "If your wallet cannot read the amount QR, use “QR address only” and type the exact amount.":
    "اگر کیف پول شما QR همراه مبلغ را نمی‌خواند، «QR فقط آدرس» را بزنید و مبلغ دقیق را دستی وارد کنید.",
  "Time left": "زمان باقی‌مانده",
  "The payment window ended. If you already sent the exact amount it will still be detected for 24 hours; otherwise create a new payment.":
    "مهلت پرداخت تمام شد. اگر مبلغ دقیق را فرستاده‌اید تا ۲۴ ساعت تشخیص داده می‌شود؛ در غیر این صورت پرداخت جدید بسازید.",
  "I have paid · check now": "پرداخت کردم · بررسی کن",
  "Simulate payment": "شبیه‌سازی پرداخت",
  "Simulate failure": "شبیه‌سازی شکست",
  "Waiting for your payment. The blockchain is checked automatically every few seconds; you do not need to refresh.":
    "در انتظار پرداخت شما. بلاک‌چین هر چند ثانیه خودکار بررسی می‌شود؛ نیازی به رفرش نیست.",
  "Payment detected: {n} of {total} network confirmations. Your plan activates automatically.":
    "پرداخت شناسایی شد: {n} از {total} تأییدیهٔ شبکه. طرح شما خودکار فعال می‌شود.",
  "We received {received} {coin}, which is {missing} {coin} less than the invoice. Send the missing difference to the same address and contact support with the transaction hash.":
    "مقدار {received} {coin} دریافت شد که {missing} {coin} کمتر از فاکتور است. مابه‌التفاوت را به همین آدرس بفرستید و هش تراکنش را به پشتیبانی بدهید.",
  "Already paid but not detected?": "پرداخت کرده‌اید ولی شناسایی نشد؟",
  "Paste the transaction hash (0x…) and we will verify it on the blockchain.":
    "هش تراکنش (0x…) را وارد کنید تا روی بلاک‌چین بررسی کنیم.",
  "Verify transaction": "بررسی تراکنش",
  "Payment confirmed. Your {plan} plan is active.": "پرداخت تأیید شد. طرح {plan} شما فعال است.",
  "Payment received after the window, accepted.": "پرداخت بعد از مهلت رسید و پذیرفته شد.",
  "This payment was {status}. You can start a new one.": "این پرداخت {status} شد. می‌توانید پرداخت جدیدی بسازید.",
  "Back to plans": "بازگشت به طرح‌ها",
  "View transaction": "مشاهدهٔ تراکنش",
  "pending": "در انتظار", "paid": "پرداخت‌شده", "failed": "ناموفق", "expired": "منقضی", "cancelled": "لغوشده",
  "Open BTCPay checkout": "باز کردن صفحهٔ پرداخت BTCPay",
  "Could not create the invoice": "ایجاد فاکتور ممکن نشد",
};

export function payT(lang: PayLang, key: string, vars?: Record<string, string | number>): string {
  let s = lang === "fa" ? PAY_FA[key] ?? key : key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

/** Assets the user may actually pick: real ones first; test ones only when the server allows them. */
export function selectableAssets(assets: CryptoAsset[]): CryptoAsset[] {
  return assets.filter((a) => a.available !== false);
}

/** Default coin/network: USDT on BEP20 when offered, else the first live asset, else the first available one. */
export function defaultAsset(assets: CryptoAsset[]): CryptoAsset | undefined {
  const list = selectableAssets(assets);
  return list.find((a) => a.id === "usdt-bep20" && a.live) ?? list.find((a) => a.live) ?? list[0];
}

export type PayStage = "awaiting" | "confirming" | "underpaid" | "window_ended" | "paid" | "closed";

export function payStage(inv: Invoice, nowMs: number): PayStage {
  if (inv.status === "paid") return "paid";
  if (inv.status !== "pending") return "closed";
  if (inv.detected) return "confirming";
  if (inv.underpaid) return "underpaid";
  if (new Date(inv.expires_at).getTime() <= nowMs) return "window_ended";
  return "awaiting";
}

export function countdownLabel(untilIso: string, nowMs: number): string {
  const left = Math.max(0, new Date(untilIso).getTime() - nowMs);
  const m = Math.floor(left / 60000);
  const s = Math.floor((left % 60000) / 1000);
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Chain key: the server's chain string ("bsc", "eth", "polygon", "tron", "btc") or, for older callers, an EVM chain id. */
export type ChainRef = string | number | null | undefined;
const ID_TO_CHAIN: Record<number, string> = { 56: "bsc", 1: "eth", 137: "polygon" };
export function chainKey(c: ChainRef): string {
  return typeof c === "number" ? ID_TO_CHAIN[c] ?? "" : c ?? "";
}
export function invChain(inv: { chain?: string | null; chain_id?: number | null }): string {
  return inv.chain || chainKey(inv.chain_id);
}

const TX_EVM = /^0x[0-9a-fA-F]{64}$/;
const TX_PLAIN = /^(0x)?[0-9a-fA-F]{64}$/;

/** Transaction link on the invoice's block explorer (Tronscan uses /transaction/, the others /tx/). */
export function txUrl(inv: Invoice, tx: string): string {
  const c = invChain(inv);
  if (!inv.explorer || !tx) return "";
  if (c === "tron") return TX_PLAIN.test(tx) ? `${inv.explorer}/transaction/${tx.replace(/^0x/, "")}` : "";
  if (c === "btc") return /^[0-9a-fA-F]{64}$/.test(tx) ? `${inv.explorer}/tx/${tx}` : "";
  return TX_EVM.test(tx) ? `${inv.explorer}/tx/${tx}` : "";
}

/** Token page on the explorer; Bitcoin has no token. */
export function tokenUrl(inv: Invoice): string {
  const c = invChain(inv);
  if (!inv.explorer || !inv.contract || c === "btc") return "";
  return c === "tron" ? `${inv.explorer}/token20/${inv.contract}` : `${inv.explorer}/token/${inv.contract}`;
}

/** Accepts 0x + 64 hex (EVM, also tolerated for Tron) or the bare 64-hex id (Tron / Bitcoin). */
export const isTxHash = (v: string) => TX_PLAIN.test(v.trim());

/** True when the server watches this invoice's chain on its own (every live asset): shows the claim box and chain details. */
export function isAutoDetected(inv: Invoice): boolean {
  if (inv.mock) return false;
  if (inv.auto_detect !== undefined) return Boolean(inv.auto_detect);
  return Boolean(inv.contract) && Boolean(inv.chain_id);
}

export function isTokenOnEvm(inv: Invoice): boolean {
  return Boolean(inv.contract) && !inv.mock && Boolean(inv.chain_id);
}

/** Stable-token amounts always show their 3 tag decimals (15.86 -> 15.860) so the exact amount is unmistakable. */
export function displayAmount(amount: string, stable: boolean): string {
  if (!stable || !/^\d+(\.\d+)?$/.test(amount)) return amount;
  const [i, f = ""] = amount.split(".");
  return `${i}.${f.padEnd(3, "0")}`;
}

export const CHAIN_BSC = 56;
export const CHAIN_ETH = 1;
export const CHAIN_POLYGON = 137;

const NOTE_TRON =
  "Tron fees are paid in TRX (or energy) that must be in your wallet: without it the transfer fails. Send USDT on the Tron (TRC20) network only; do not use ERC20, BEP20 or Polygon for this address, those coins would be lost.";
const NOTE_BTC =
  "Send the exact BTC amount shown in ONE on-chain transaction, with the network fee paid on top (do not choose “subtract fee from amount”). Lightning is not supported. The amount is fixed at the price when you created this payment; the last digits identify your invoice. Bitcoin needs {n} confirmations, usually about 30 minutes or more.";

/** Per-network warning (English key; run it through payT; the Bitcoin one has an {n} variable). Empty for unknown chains. */
export function networkNote(chain?: ChainRef): string {
  switch (chainKey(chain)) {
    case "eth":
      return "Ethereum network fees (gas) are high: often several dollars up to tens of dollars, paid in ETH that must be in your wallet, and they can be more than the cost of a small plan. If you can, choose BNB Smart Chain (BEP20) or Polygon, which cost cents. Confirmation takes a few minutes.";
    case "polygon":
      return "Polygon fees are very low, paid in a little POL that must be in your wallet. Send native Polygon PoS tokens only (for USDC: the native “USDC”, not the older bridged “USDC.e”). Some wallets show Polygon USDT as “USDT0”: it is the same Tether token, send it normally.";
    case "bsc":
      return "BEP20 is cheap: the network fee is a few cents, paid in a little BNB that must be in your wallet. Do not send from or to Ethereum, Polygon or Tron addresses: those coins would be lost.";
    case "tron":
      return NOTE_TRON;
    case "btc":
      return NOTE_BTC;
    default:
      return "";
  }
}

export function isHighFeeChain(chain?: ChainRef): boolean {
  return chainKey(chain) === "eth";
}

export function explorerLabel(chain?: ChainRef): string {
  switch (chainKey(chain)) {
    case "eth":
      return "Verify on Etherscan";
    case "polygon":
      return "Verify on PolygonScan";
    case "tron":
      return "Verify on Tronscan";
    case "btc":
      return "Verify on mempool.space";
    default:
      return "Verify on BscScan";
  }
}

const BLOCK_SECONDS: Record<string, number> = { bsc: 0.45, polygon: 2.1, eth: 12, tron: 3, btc: 600 };

/** "Needs N confirmations (about 2 minutes)" for a chain, using its block time. */
export function confirmEta(chain: ChainRef, confirmations: number): { n: number; seconds: number } {
  const bt = BLOCK_SECONDS[chainKey(chain)] || 3;
  return { n: confirmations, seconds: Math.max(5, Math.round(confirmations * bt)) };
}

export function etaText(lang: PayLang, seconds: number): string {
  return seconds < 90 ? payT(lang, "{n} seconds", { n: seconds }) : payT(lang, "{n} minutes", { n: Math.round(seconds / 60) });
}
