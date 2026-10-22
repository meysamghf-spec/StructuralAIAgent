"use client";

import {
  fmtToman,
  getBillingPlans,
  getInvoice,
  mockConfirmInvoice,
  startCheckout,
  type Catalog,
  type CryptoAsset,
  type Invoice,
} from "@/lib/billing";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

function useCountdown(until?: string) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!until) return { left: 0, label: "" };
  const left = Math.max(0, new Date(until).getTime() - now);
  const m = Math.floor(left / 60000);
  const s = Math.floor((left % 60000) / 1000);
  return { left, label: `${m}:${String(s).padStart(2, "0")}` };
}

function Copy({ text, testId }: { text: string; testId: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="button secondary billing-copy"
      data-testid={testId}
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setDone(true));
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? "Copied" : "Copy"}
    </button>
  );
}

function PayInner() {
  const params = useSearchParams();
  const planId = params.get("plan") ?? "pro";
  const durationId = params.get("duration") ?? "1m";
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [coin, setCoin] = useState("USDT");
  const [assetId, setAssetId] = useState("usdt-trc20");
  const [inv, setInv] = useState<Invoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { left, label } = useCountdown(inv?.expires_at);

  useEffect(() => {
    getBillingPlans().then(setCatalog).catch((e) => setError(String(e?.message ?? e)));
    const existing = params.get("invoice");
    if (existing) getInvoice(existing).then((r) => setInv(r.invoice)).catch(() => undefined);
  }, [params]);

  // poll the chain watcher while pending
  useEffect(() => {
    if (!inv || inv.status !== "pending" || inv.mock) return;
    const t = setInterval(() => {
      getInvoice(inv.id).then((r) => setInv((old) => ({ ...r.invoice, qr_svg: r.invoice.qr_svg ?? old?.qr_svg }))).catch(() => undefined);
    }, 15000);
    return () => clearInterval(t);
  }, [inv]);

  const plan = catalog?.plans.find((p) => p.id === planId);
  const q = plan?.quotes?.[durationId];
  const coins = useMemo(() => Array.from(new Set((catalog?.assets ?? []).map((a) => a.coin))), [catalog]);
  const networks: CryptoAsset[] = (catalog?.assets ?? []).filter((a) => a.coin === coin);
  const asset = catalog?.assets.find((a) => a.id === assetId);

  function pickCoin(c: string) {
    setCoin(c);
    const first = catalog?.assets.find((a) => a.coin === c);
    if (first) setAssetId(first.id);
  }

  async function create() {
    setBusy(true);
    setError("");
    try {
      const r = await startCheckout(planId, durationId, assetId);
      setInv(r.invoice);
      if (r.invoice.checkout_url) window.open(r.invoice.checkout_url, "_blank", "noopener");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create the invoice");
    } finally {
      setBusy(false);
    }
  }

  async function simulate(ok: boolean) {
    if (!inv) return;
    setBusy(true);
    try {
      setInv((await mockConfirmInvoice(inv.id, ok)).invoice);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  }

  async function check() {
    if (!inv) return;
    setBusy(true);
    try {
      const r = await getInvoice(inv.id);
      setInv((old) => ({ ...r.invoice, qr_svg: r.invoice.qr_svg ?? old?.qr_svg }));
    } finally {
      setBusy(false);
    }
  }

  const doneHref = inv ? `/workspace/upgrades?invoice=${inv.number}&status=${inv.status}` : "/workspace/upgrades";

  return (
    <div className="workspace-page billing-page">
      <section className="workspace-card">
        <p className="eyebrow">
          <Link href="/workspace/upgrades">← Plans</Link>
        </p>
        <h1>Pay with crypto</h1>
        {plan && q ? (
          <p className="workspace-help" data-testid="pay-summary">
            {plan.name} · {q.months} month{q.months > 1 ? "s" : ""}: <strong>{q.amount_usdt} USDT</strong>{" "}
            <span className="billing-ref">≈ {fmtToman(q.amount_toman)} (reference)</span>
          </p>
        ) : null}
      </section>
      {error ? <p className="workspace-error">{error}</p> : null}

      {!inv && catalog ? (
        <section className="workspace-card" data-testid="asset-picker">
          <h2>1. Coin</h2>
          <div className="billing-chips" role="group" aria-label="Coin">
            {coins.map((c) => (
              <button key={c} type="button" className={c === coin ? "active" : ""} onClick={() => pickCoin(c)} data-testid={`coin-${c}`}>
                {c}
              </button>
            ))}
          </div>
          <h2>2. Network</h2>
          <div className="billing-chips" role="group" aria-label="Network">
            {networks.map((a) => (
              <button
                key={a.id}
                type="button"
                className={a.id === assetId ? "active" : ""}
                onClick={() => setAssetId(a.id)}
                data-testid={`net-${a.id}`}
              >
                {a.network}
                {a.live ? "" : " · test"}
              </button>
            ))}
          </div>
          {asset ? <p className="workspace-meta">Processed by: {asset.processor}</p> : null}
          <button type="button" className="workspace-primary-button" disabled={busy} onClick={() => void create()} data-testid="create-invoice">
            {busy ? "Creating…" : "Create payment"}
          </button>
        </section>
      ) : null}

      {inv ? (
        <section className="workspace-card billing-pay" data-testid="invoice-panel">
          <div className="billing-pay-head">
            <h2>
              Invoice {inv.number}
            </h2>
            <span className={`billing-st ${inv.status}`} data-testid="invoice-status">
              {inv.status}
            </span>
          </div>
          {inv.status === "pending" ? (
            <>
              {inv.mock ? (
                <p className="billing-mock-note" data-testid="mock-note">
                  Test invoice: this wallet is not configured yet, so the address below is a placeholder. Do not send real
                  coins. Use “Simulate payment”.
                </p>
              ) : null}
              <p className="billing-warn" data-testid="network-warning">
                ⚠ Send only <strong>{inv.coin}</strong> on <strong>{inv.network}</strong>
                {inv.standard !== "native" && inv.standard !== "Lightning" ? ` (${inv.standard})` : ""}. Coins sent on any
                other network, or a different token, will be lost. Send the exact amount (the last digits identify your
                invoice).
              </p>
              {inv.checkout_url ? (
                <p>
                  <a className="workspace-primary-button" href={inv.checkout_url} target="_blank" rel="noreferrer">
                    Open BTCPay checkout
                  </a>
                </p>
              ) : (
                <div className="billing-pay-grid">
                  {inv.qr_svg ? (
                    <div className="billing-qr" data-testid="pay-qr" dangerouslySetInnerHTML={{ __html: inv.qr_svg }} />
                  ) : null}
                  <dl className="billing-pay-fields">
                    <div>
                      <dt>Amount</dt>
                      <dd>
                        <code data-testid="pay-amount">
                          {inv.amount_crypto} {inv.coin}
                        </code>
                        <Copy text={inv.amount_crypto} testId="copy-amount" />
                      </dd>
                    </div>
                    <div>
                      <dt>Address</dt>
                      <dd>
                        <code className="billing-addr" data-testid="pay-address">
                          {inv.pay_address}
                        </code>
                        <Copy text={inv.pay_address} testId="copy-address" />
                      </dd>
                    </div>
                    {inv.rate_usd && inv.coin !== "USDT" && inv.coin !== "USDC" ? (
                      <div>
                        <dt>Rate</dt>
                        <dd>
                          1 {inv.coin} = {inv.rate_usd.toLocaleString("en-US")} USD ({inv.rate_source}), locked until expiry
                        </dd>
                      </div>
                    ) : null}
                  </dl>
                </div>
              )}
              <p className="billing-timer" data-testid="pay-timer">
                {left > 0 ? (
                  <>
                    Expires in <strong>{label}</strong>
                  </>
                ) : (
                  "Expired. Create a new payment, or contact support if you already sent coins."
                )}
              </p>
              <div className="form-row">
                <button type="button" className="button secondary" disabled={busy} onClick={() => void check()} data-testid="check-payment">
                  I have paid · check now
                </button>
                {inv.mock ? (
                  <>
                    <button type="button" className="button" disabled={busy} onClick={() => void simulate(true)} data-testid="mock-pay">
                      Simulate payment
                    </button>
                    <button type="button" className="button secondary" disabled={busy} onClick={() => void simulate(false)} data-testid="mock-cancel">
                      Simulate failure
                    </button>
                  </>
                ) : (
                  <span className="workspace-meta">We check the blockchain every 15 s; confirmation usually takes 1–5 min.</span>
                )}
              </div>
            </>
          ) : (
            <>
              <p data-testid="pay-result" className={inv.status === "paid" ? "billing-banner ok" : "billing-banner bad"}>
                {inv.status === "paid"
                  ? `Payment confirmed${inv.tx ? ` (tx ${inv.tx.slice(0, 18)}…)` : ""}. Your ${inv.plan_name} plan is active.`
                  : `This payment was ${inv.status}. You can start a new one.`}
              </p>
              <Link className="workspace-primary-button" href={doneHref} data-testid="pay-done">
                Back to plans
              </Link>
            </>
          )}
        </section>
      ) : null}
    </div>
  );
}

export default function PayClient() {
  return (
    <Suspense fallback={null}>
      <PayInner />
    </Suspense>
  );
}
