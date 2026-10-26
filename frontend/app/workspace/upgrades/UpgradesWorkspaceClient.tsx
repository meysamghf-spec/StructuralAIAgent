"use client";

import {
  fmtLimit,
  fmtStorage,
  fmtToman,
  getBillingAccount,
  getBillingPlans,
  type BillingAccount,
  type Catalog,
  type Plan,
} from "@/lib/billing";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

const SHEET_LABEL: Record<string, string> = {
  mabhas9_check: "Mabhas 9 checks",
  seismic_2800: "Standard 2800 seismic",
  rebar_sheets: "Rebar sheets",
};

function limitRows(p: Plan): [string, string][] {
  const l = p.limits;
  return [
    ["Projects", fmtLimit(l.projects)],
    ["Analyses / month", fmtLimit(l.analyses_per_month)],
    [
      "3D frame size",
      l.frame_max_storeys === null ? "Unlimited" : `${l.frame_max_storeys} storeys × ${l.frame_max_bays} bays`,
    ],
    ["Design sheets", l.design_sheets.map((s) => SHEET_LABEL[s] ?? s).join(", ") || "—"],
    ["Exports", l.exports.length ? l.exports.map((e) => (e === "dxf" ? "DXF" : e === "e2k" ? "ETABS" : e === "s2k" ? "SAP2000" : "SAFE")).join(", ") : "—"],
    ["AutoCAD imports / month", fmtLimit(l.autocad_imports_per_month)],
    ["Optimization", l.optimization ? "Included" : "—"],
    ["Seats", fmtLimit(l.seats)],
    ["Storage", fmtStorage(l.storage_mb)],
    ["Support", l.support],
  ];
}

function UpgradesInner() {
  const params = useSearchParams();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [account, setAccount] = useState<BillingAccount | null>(null);
  const [duration, setDuration] = useState("12m");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [c, a] = await Promise.all([getBillingPlans(), getBillingAccount()]);
    setCatalog(c);
    setAccount(a);
  }, []);
  useEffect(() => {
    void load().catch((e) => setError(e instanceof Error ? e.message : "Could not load plans"));
  }, [load]);

  function buy(plan: Plan) {
    setBusy(plan.id);
    window.location.href = `/workspace/upgrades/pay?plan=${plan.id}&duration=${duration}`;
  }

  const status = params.get("status");
  const invNo = params.get("invoice");
  const current = account?.plan.id ?? "free";
  const sub = account?.subscription;

  return (
    <div className="workspace-page billing-page">
      <section className="workspace-card">
        <h1>Plans &amp; billing</h1>
        <p className="workspace-help">
          Pick a plan for your engineering work. Pay with crypto: USDT or USDC (Tron, BSC, Ethereum, Polygon), BTC (on-chain or
          Lightning), ETH, TRX, BNB, TON or LTC. Prices are in USDT; toman is shown for reference. Longer terms are discounted.
        </p>
        {account?.payments.mock ? (
          <p className="billing-mock-note" data-testid="mock-note">
            Test mode: crypto payments are simulated until receiving wallets are configured. No real money moves.
          </p>
        ) : null}
      </section>

      {status ? (
        <p className={status === "paid" ? "billing-banner ok" : "billing-banner bad"} data-testid="pay-result">
          {status === "paid"
            ? `Payment received (invoice ${invNo}). Your plan is active.`
            : `Payment was not completed (invoice ${invNo}, ${status}). If you already sent coins, contact support with the invoice number and transaction hash.`}
        </p>
      ) : null}
      {error ? <p className="workspace-error">{error}</p> : null}

      {account ? (
        <section className="workspace-card billing-current" data-testid="current-plan">
          <h2>Your plan: {account.plan.name}</h2>
          {sub ? (
            <p>
              Active until <strong>{new Date(sub.expires_at).toLocaleDateString()}</strong>. Buying the same plan again
              extends this date; buying a different plan switches now.
            </p>
          ) : account.complimentary ? (
            <p>Complimentary access.</p>
          ) : (
            <p>Free plan. Upgrade any time; when a paid plan ends you return to Free.</p>
          )}
          <div className="billing-usage">
            <span>
              Analyses this month: <strong>{account.usage.analyses_per_month}</strong> /{" "}
              {fmtLimit(account.plan.limits.analyses_per_month)}
            </span>
            <span>
              AutoCAD imports this month: <strong>{account.usage.autocad_imports_per_month}</strong> /{" "}
              {fmtLimit(account.plan.limits.autocad_imports_per_month)}
            </span>
          </div>
        </section>
      ) : null}

      {catalog ? (
        <>
          <div className="billing-toggles">
            <div className="billing-seg" role="group" aria-label="Billing period">
              {catalog.durations.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  className={duration === d.id ? "active" : ""}
                  onClick={() => setDuration(d.id)}
                >
                  {d.label}
                  {d.discount_pct ? <em>−{d.discount_pct}%</em> : null}
                </button>
              ))}
            </div>
          </div>

          <section className="billing-grid">
            {catalog.plans.map((p) => {
              const q = p.quotes?.[duration];
              const isCurrent = p.id === current;
              return (
                <article key={p.id} className={`billing-plan${p.highlight ? " highlight" : ""}`} data-plan={p.id}>
                  {p.highlight ? <span className="billing-badge">Most popular</span> : null}
                  <h3>
                    {p.name} {p.name_fa ? <small lang="fa">{p.name_fa}</small> : null}
                  </h3>
                  <p className="workspace-meta">{p.tagline}</p>
                  <div className="billing-price">
                    {!p.purchasable || !q ? (
                      <strong>Free</strong>
                    ) : (
                      <>
                        <strong>{q.amount_usdt.toLocaleString("en-US")} USDT</strong>
                        <span>
                          for {q.months} month{q.months > 1 ? "s" : ""}
                          {q.discount_pct ? <s> {q.list_usdt} USDT</s> : null}
                        </span>
                        <span className="billing-ref">≈ {fmtToman(q.amount_toman)} (reference)</span>
                      </>
                    )}
                  </div>
                  <dl className="billing-limits">
                    {limitRows(p).map(([k, v]) => (
                      <div key={k}>
                        <dt>{k}</dt>
                        <dd>{v}</dd>
                      </div>
                    ))}
                  </dl>
                  {p.purchasable ? (
                    <button
                      type="button"
                      className="workspace-primary-button"
                      disabled={!!busy}
                      onClick={() => void buy(p)}
                      data-testid={`buy-${p.id}`}
                    >
                      {busy === p.id
                        ? "Opening…"
                        : isCurrent
                          ? `Renew ${p.name}`
                          : `Get ${p.name} · Pay with crypto`}
                    </button>
                  ) : (
                    <p className="workspace-meta">{isCurrent ? "Your current plan" : "Included for everyone"}</p>
                  )}
                </article>
              );
            })}
          </section>
        </>
      ) : null}

      {account ? (
        <section className="workspace-card" data-testid="invoices">
          <h2>Invoices</h2>
          {account.invoices.length === 0 ? (
            <p className="workspace-help">No invoices yet.</p>
          ) : (
            <div className="billing-table-wrap">
              <table className="billing-table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Plan</th>
                    <th>Amount</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {account.invoices.map((i) => (
                    <tr key={i.id}>
                      <td>{i.number}</td>
                      <td>
                        {i.plan_name} · {i.months} mo
                      </td>
                      <td>
                        {i.amount_usdt} USDT
                        {i.amount_crypto && i.coin !== "USDT" ? ` (${i.amount_crypto} ${i.coin})` : ""}
                      </td>
                      <td>
                        {i.coin} · {i.standard === "native" ? i.network : i.standard}
                        {i.mock ? " (test)" : ""}
                      </td>
                      <td className={`billing-st ${i.status}`}>{i.status}</td>
                      <td>{new Date(i.paid_at ?? i.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {account.history.length ? (
            <>
              <h3>Subscription history</h3>
              <ul className="workspace-list">
                {account.history.map((h, k) => (
                  <li key={k}>
                    {new Date(h.at).toLocaleDateString()}: {h.action} {h.plan_id}, until{" "}
                    {new Date(h.expires_at).toLocaleDateString()} ({h.invoice})
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

export default function UpgradesWorkspaceClient() {
  return (
    <Suspense fallback={null}>
      <UpgradesInner />
    </Suspense>
  );
}
