"use client";

import { useUiLang } from "@/hooks/useUiLang";
import {
  claimInvoiceTx,
  fmtToman,
  getBillingPlans,
  getInvoice,
  mockConfirmInvoice,
  startCheckout,
  type Catalog,
  type CryptoAsset,
  type Invoice,
} from "@/lib/billing";
import { confirmEta, countdownLabel, defaultAsset, displayAmount, etaText, explorerLabel, invChain, isAutoDetected, isHighFeeChain, isTxHash, networkNote, payStage, payT, selectableAssets, tokenUrl, txUrl } from "@/lib/crypto-pay";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

function useNow() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function Copy({ text, testId, label, done }: { text: string; testId: string; label: string; done: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      type="button"
      className="button secondary billing-copy"
      data-testid={testId}
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setOk(true));
        setTimeout(() => setOk(false), 1500);
      }}
    >
      {ok ? done : label}
    </button>
  );
}

function PayInner() {
  const params = useSearchParams();
  const { lang } = useUiLang();
  const tr = useCallback((k: string, v?: Record<string, string | number>) => payT(lang, k, v), [lang]);
  const planId = params.get("plan") ?? "pro";
  const durationId = params.get("duration") ?? "1m";
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [coin, setCoin] = useState("");
  const [assetId, setAssetId] = useState("");
  const [inv, setInv] = useState<Invoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [qrMode, setQrMode] = useState<"amount" | "address">("amount");
  const [txInput, setTxInput] = useState("");
  const now = useNow();

  const merge = useCallback((next: Invoice) => setInv((old) => ({ ...next, qr_svg: next.qr_svg ?? old?.qr_svg, qr_address_svg: next.qr_address_svg ?? old?.qr_address_svg })), []);

  useEffect(() => {
    getBillingPlans()
      .then((c) => {
        setCatalog(c);
        const d = defaultAsset(c.assets);
        if (d) {
          setCoin(d.coin);
          setAssetId(d.id);
        }
      })
      .catch((e) => setError(String(e?.message ?? e)));
    const existing = params.get("invoice");
    if (existing) getInvoice(existing).then((r) => setInv(r.invoice)).catch(() => undefined);
  }, [params]);

  // poll while pending: the server watcher does the chain work, this only refreshes the status
  const invId = inv?.id;
  const invPending = inv?.status === "pending" && !inv.mock;
  useEffect(() => {
    if (!invId || !invPending) return;
    const t = setInterval(() => {
      getInvoice(invId).then((r) => merge(r.invoice)).catch(() => undefined);
    }, 6000);
    return () => clearInterval(t);
  }, [invId, invPending, merge]);

  const plan = catalog?.plans.find((p) => p.id === planId);
  const q = plan?.quotes?.[durationId];
  const assets = useMemo(() => selectableAssets(catalog?.assets ?? []), [catalog]);
  const coins = useMemo(() => Array.from(new Set(assets.map((a) => a.coin))), [assets]);
  const networks: CryptoAsset[] = assets.filter((a) => a.coin === coin);
  const asset = assets.find((a) => a.id === assetId);

  function pickCoin(c: string) {
    setCoin(c);
    const first = assets.find((a) => a.coin === c);
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
      setError(e instanceof Error ? e.message : tr("Could not create the invoice"));
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
    setError("");
    try {
      merge((await getInvoice(inv.id)).invoice);
    } catch (e) {
      setError(e instanceof Error ? e.message : "");
    } finally {
      setBusy(false);
    }
  }

  async function claim() {
    if (!inv || !isTxHash(txInput)) return;
    setBusy(true);
    setError("");
    try {
      merge((await claimInvoiceTx(inv.id, txInput.trim())).invoice);
    } catch (e) {
      setError(e instanceof Error ? e.message : "");
    } finally {
      setBusy(false);
    }
  }

  const dir = lang === "fa" ? "rtl" : "ltr";
  const doneHref = inv ? `/workspace/upgrades?invoice=${inv.number}&status=${inv.status}` : "/workspace/upgrades";
  const stage = inv ? payStage(inv, now) : "awaiting";
  const watched = inv ? isAutoDetected(inv) : false;
  const chain = inv ? invChain(inv) : "";
  const qr = inv ? (qrMode === "address" && inv.qr_address_svg ? inv.qr_address_svg : inv.qr_svg) : "";
  const label = inv ? countdownLabel(inv.expires_at, now) : "";
  const net = inv ? tr(inv.network) : "";

  return (
    <div className={`workspace-page billing-page billing-pay-page${lang === "fa" ? " is-rtl" : ""}`} dir={dir} lang={lang} data-testid="pay-root">
      <section className="workspace-card">
        <p className="eyebrow">
          <Link href="/workspace/upgrades">{tr("← Plans")}</Link>
        </p>
        <h1>{tr("Pay with crypto")}</h1>
        {plan && q ? (
          <p className="workspace-help" data-testid="pay-summary">
            {lang === "fa" && plan.name_fa ? plan.name_fa : plan.name} · {q.months} {tr(q.months > 1 ? "months" : "month")}:{" "}
            <strong dir="ltr">{q.amount_usdt} USDT</strong>{" "}
            <span className="billing-ref">
              ≈ {fmtToman(q.amount_toman)} {tr("(reference)")}
            </span>
          </p>
        ) : null}
      </section>
      {error ? <p className="workspace-error" data-testid="pay-error">{error}</p> : null}

      {!inv && catalog ? (
        <section className="workspace-card" data-testid="asset-picker">
          {assets.length === 0 ? (
            <p className="workspace-help">{tr("No payment method is available right now. Please try again later.")}</p>
          ) : (
            <>
              <h2>{tr("1. Coin")}</h2>
              <div className="billing-chips" role="group" aria-label="Coin">
                {coins.map((c) => (
                  <button key={c} type="button" className={c === coin ? "active" : ""} onClick={() => pickCoin(c)} data-testid={`coin-${c}`}>
                    {c}
                  </button>
                ))}
              </div>
              <h2>{tr("2. Network")}</h2>
              <div className="billing-chips" role="group" aria-label="Network">
                {networks.map((a) => (
                  <button key={a.id} type="button" className={a.id === assetId ? "active" : ""} onClick={() => setAssetId(a.id)} data-testid={`net-${a.id}`}>
                    {tr(a.network)}
                    {a.live ? "" : " · test"}
                  </button>
                ))}
              </div>
              {asset ? (
                <p className="workspace-meta">
                  {tr("Processed by")}: {asset.processor}
                </p>
              ) : null}
              {asset?.live && (asset.contract || asset.chain === "btc") ? (
                <p className="billing-warn" data-testid="pre-warning">
                  {tr("Send only {coin} on {network}. Any other token or network will be lost and cannot be recovered. Send exactly the amount shown, including the last digits: they identify your invoice.", {
                    coin: asset.coin,
                    network: tr(asset.network),
                  })}
                </p>
              ) : null}
              {asset?.live && (asset.contract || asset.chain === "btc") && networkNote(asset.chain ?? asset.chain_id) ? (
                <p className={`billing-warn${isHighFeeChain(asset.chain ?? asset.chain_id) ? " billing-warn-fee" : " billing-note"}`} data-testid="network-note">
                  {isHighFeeChain(asset.chain ?? asset.chain_id) ? "⛽ " : "ℹ "}
                  {tr(networkNote(asset.chain ?? asset.chain_id), { n: asset.confirmations ?? 3 })}
                </p>
              ) : null}
              {asset?.live && (asset.contract || asset.chain === "btc") && asset.confirmations ? (
                <p className="workspace-meta" data-testid="confirm-eta">
                  {tr("Needs {n} network confirmations (about {time}).", {
                    n: asset.confirmations,
                    time: etaText(lang, confirmEta(asset.chain ?? asset.chain_id, asset.confirmations).seconds),
                  })}
                </p>
              ) : null}
              <button type="button" className="workspace-primary-button" disabled={busy || !assetId} onClick={() => void create()} data-testid="create-invoice">
                {busy ? tr("Creating…") : tr("Create payment")}
              </button>
            </>
          )}
        </section>
      ) : null}

      {inv ? (
        <section className="workspace-card billing-pay" data-testid="invoice-panel">
          <div className="billing-pay-head">
            <h2>
              {tr("Invoice")} <span dir="ltr">{inv.number}</span>
            </h2>
            <span className={`billing-st ${inv.status}`} data-testid="invoice-status">
              {tr(inv.status)}
            </span>
          </div>
          {inv.status === "pending" ? (
            <>
              {inv.mock ? (
                <p className="billing-mock-note" data-testid="mock-note">
                  {tr("Test invoice: this wallet is not configured yet, so the address below is a placeholder. Do not send real coins. Use “Simulate payment”.")}
                </p>
              ) : null}
              {watched ? (
                <div className="billing-netbox" data-testid="network-box">
                  <span>
                    {tr("Network")}: <strong data-testid="net-name">{net}</strong>
                  </span>
                  <span>
                    {tr(inv.contract ? "Token" : "Coin")}: <strong dir="ltr">{inv.coin}</strong>
                  </span>
                </div>
              ) : null}
              <p className="billing-warn" data-testid="network-warning">
                ⚠{" "}
                {tr("Send only {coin} on {network}. Any other token or network will be lost and cannot be recovered. Send exactly the amount shown, including the last digits: they identify your invoice.", {
                  coin: inv.coin,
                  network: net,
                })}
              </p>
              {watched && networkNote(chain) ? (
                <p className={`billing-warn${isHighFeeChain(chain) ? " billing-warn-fee" : " billing-note"}`} data-testid="network-note-invoice">
                  {isHighFeeChain(chain) ? "⛽ " : "ℹ "}
                  {tr(networkNote(chain), { n: inv.confirmations_required ?? 3 })}
                </p>
              ) : null}
              {inv.checkout_url ? (
                <p>
                  <a className="workspace-primary-button" href={inv.checkout_url} target="_blank" rel="noreferrer">
                    {tr("Open BTCPay checkout")}
                  </a>
                </p>
              ) : (
                <div className="billing-pay-grid">
                  {qr ? (
                    <div>
                      <div className="billing-qr" data-testid="pay-qr" dangerouslySetInnerHTML={{ __html: qr }} />
                      {inv.qr_address_svg ? (
                        <>
                          <div className="billing-chips billing-qr-tabs" role="group" aria-label="QR">
                            <button type="button" className={qrMode === "amount" ? "active" : ""} onClick={() => setQrMode("amount")} data-testid="qr-amount">
                              {tr("QR with amount")}
                            </button>
                            <button type="button" className={qrMode === "address" ? "active" : ""} onClick={() => setQrMode("address")} data-testid="qr-address">
                              {tr("QR address only")}
                            </button>
                          </div>
                          <p className="workspace-meta">{tr("If your wallet cannot read the amount QR, use “QR address only” and type the exact amount.")}</p>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  <dl className="billing-pay-fields">
                    <div>
                      <dt>{tr("Amount")}</dt>
                      <dd>
                        <code className="billing-amount" dir="ltr" data-testid="pay-amount">
                          {displayAmount(inv.amount_crypto, inv.coin === "USDT" || inv.coin === "USDC")} {inv.coin}
                        </code>
                        <Copy text={inv.amount_crypto} testId="copy-amount" label={tr("Copy")} done={tr("Copied")} />
                      </dd>
                    </div>
                    <div>
                      <dt>{tr("Address")}</dt>
                      <dd>
                        <code className="billing-addr" dir="ltr" data-testid="pay-address">
                          {inv.pay_address}
                        </code>
                        <Copy text={inv.pay_address} testId="copy-address" label={tr("Copy")} done={tr("Copied")} />
                      </dd>
                    </div>
                    {watched && inv.contract ? (
                      <div>
                        <dt>{tr("Token contract")}</dt>
                        <dd>
                          <code className="billing-addr" dir="ltr" data-testid="pay-contract">
                            {inv.contract}
                          </code>
                          <Copy text={inv.contract} testId="copy-contract" label={tr("Copy")} done={tr("Copied")} />
                          {tokenUrl(inv) ? (
                            <a href={tokenUrl(inv)} target="_blank" rel="noreferrer" className="billing-link">
                              {tr(explorerLabel(chain))}
                            </a>
                          ) : null}
                        </dd>
                      </div>
                    ) : null}
                    {inv.rate_usd && inv.coin !== "USDT" && inv.coin !== "USDC" ? (
                      <div>
                        <dt>{tr("Rate")}</dt>
                        <dd>
                          1 {inv.coin} = {inv.rate_usd.toLocaleString("en-US")} USD ({inv.rate_source}), {tr("locked until expiry")}
                        </dd>
                      </div>
                    ) : null}
                  </dl>
                </div>
              )}
              <p className="billing-timer" data-testid="pay-timer">
                {stage === "window_ended" ? (
                  tr("The payment window ended. If you already sent the exact amount it will still be detected for 24 hours; otherwise create a new payment.")
                ) : (
                  <>
                    {tr("Time left")}: <strong dir="ltr">{label}</strong>
                  </>
                )}
              </p>
              {stage === "confirming" && inv.detected ? (
                <p className="billing-banner ok" data-testid="pay-confirming">
                  {tr("Payment detected: {n} of {total} network confirmations. Your plan activates automatically.", {
                    n: inv.detected.confirmations,
                    total: inv.detected.required,
                  })}{" "}
                  {txUrl(inv, inv.detected.tx) ? (
                    <a href={txUrl(inv, inv.detected.tx)} target="_blank" rel="noreferrer" className="billing-link">
                      {tr("View transaction")}
                    </a>
                  ) : null}
                </p>
              ) : null}
              {stage === "underpaid" && inv.underpaid ? (
                <p className="billing-banner bad" data-testid="pay-underpaid">
                  {tr("We received {received} {coin}, which is {missing} {coin} less than the invoice. Send the missing difference to the same address and contact support with the transaction hash.", {
                    received: inv.underpaid.received,
                    missing: inv.underpaid.missing,
                    coin: inv.coin,
                  })}
                </p>
              ) : null}
              {stage === "awaiting" && !inv.mock ? (
                <p className="workspace-meta" data-testid="pay-waiting">
                  {tr("Waiting for your payment. The blockchain is checked automatically every few seconds; you do not need to refresh.")}
                </p>
              ) : null}
              <div className="form-row">
                <button type="button" className="button secondary" disabled={busy} onClick={() => void check()} data-testid="check-payment">
                  {tr("I have paid · check now")}
                </button>
                {inv.mock ? (
                  <>
                    <button type="button" className="button" disabled={busy} onClick={() => void simulate(true)} data-testid="mock-pay">
                      {tr("Simulate payment")}
                    </button>
                    <button type="button" className="button secondary" disabled={busy} onClick={() => void simulate(false)} data-testid="mock-cancel">
                      {tr("Simulate failure")}
                    </button>
                  </>
                ) : null}
              </div>
              {watched ? (
                <details className="billing-claim" data-testid="claim-box">
                  <summary>{tr("Already paid but not detected?")}</summary>
                  <p className="workspace-meta">
                    {tr(chain === "tron" || chain === "btc" ? "Paste the transaction id (64 characters) and we will verify it on the blockchain." : "Paste the transaction hash (0x…) and we will verify it on the blockchain.")}
                  </p>
                  <div className="form-row">
                    <input
                      className="billing-tx-input"
                      dir="ltr"
                      placeholder={chain === "tron" || chain === "btc" ? "64-character id" : "0x…"}
                      value={txInput}
                      onChange={(e) => setTxInput(e.target.value)}
                      data-testid="claim-input"
                      spellCheck={false}
                    />
                    <button type="button" className="button" disabled={busy || !isTxHash(txInput)} onClick={() => void claim()} data-testid="claim-submit">
                      {tr("Verify transaction")}
                    </button>
                  </div>
                </details>
              ) : null}
            </>
          ) : (
            <>
              <p data-testid="pay-result" className={inv.status === "paid" ? "billing-banner ok" : "billing-banner bad"}>
                {inv.status === "paid"
                  ? tr("Payment confirmed. Your {plan} plan is active.", { plan: inv.plan_name })
                  : tr("This payment was {status}. You can start a new one.", { status: tr(inv.status) })}
                {inv.status === "paid" && inv.paid_late ? ` ${tr("Payment received after the window, accepted.")}` : ""}{" "}
                {inv.status === "paid" && inv.tx && txUrl(inv, inv.tx) ? (
                  <a href={txUrl(inv, inv.tx)} target="_blank" rel="noreferrer" className="billing-link" data-testid="pay-tx-link">
                    {tr("View transaction")}
                  </a>
                ) : null}
              </p>
              <Link className="workspace-primary-button" href={doneHref} data-testid="pay-done">
                {tr("Back to plans")}
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
