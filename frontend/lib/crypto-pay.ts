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
  "BNB Smart Chain (BEP20)": "بایننس اسمارت چین (BEP20)",
  "Send only {coin} on {network}. Any other token or network (for example TRC20 or ERC20) will be lost and cannot be recovered. Send exactly the amount shown, including the last digits: they identify your invoice.":
    "فقط {coin} روی شبکهٔ {network} بفرستید. هر توکن یا شبکهٔ دیگر (مثلاً TRC20 یا ERC20) از بین می‌رود و قابل بازیابی نیست. دقیقاً همان مبلغ نمایش‌داده‌شده را با همهٔ ارقام اعشار بفرستید؛ رقم‌های آخر، فاکتور شما را مشخص می‌کنند.",
  "Amount": "مبلغ",
  "Address": "آدرس",
  "Token contract": "قرارداد توکن",
  "Verify on BscScan": "بررسی در BscScan",
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

export function txUrl(inv: Invoice, tx: string): string {
  return inv.explorer && /^0x[0-9a-fA-F]{64}$/.test(tx) ? `${inv.explorer}/tx/${tx}` : "";
}

export const isTxHash = (v: string) => /^0x[0-9a-fA-F]{64}$/.test(v.trim());

export function isTokenOnEvm(inv: Invoice): boolean {
  return Boolean(inv.contract) && !inv.mock && Boolean(inv.chain_id);
}

/** Stable-token amounts always show their 3 tag decimals (15.86 -> 15.860) so the exact amount is unmistakable. */
export function displayAmount(amount: string, stable: boolean): string {
  if (!stable || !/^\d+(\.\d+)?$/.test(amount)) return amount;
  const [i, f = ""] = amount.split(".");
  return `${i}.${f.padEnd(3, "0")}`;
}
