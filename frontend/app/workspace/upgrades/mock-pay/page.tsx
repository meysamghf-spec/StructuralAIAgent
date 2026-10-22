"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function MockPay() {
  const q = useSearchParams();
  const callback = q.get("callback") ?? "";
  const gateway = q.get("gateway") ?? "";
  const amount = Number(q.get("amount") ?? 0);
  const isCard = gateway.startsWith("card");
  const go = (ok: boolean) => {
    if (!callback.startsWith(window.location.origin)) return;
    const u = new URL(callback);
    u.searchParams.set("Status", ok ? "OK" : "NOK");
    u.searchParams.set("Authority", q.get("authority") ?? "");
    window.location.href = u.toString();
  };
  return (
    <div className="workspace-page billing-page">
      <section className="workspace-card billing-mockpay">
        <p className="billing-mock-note">Simulated gateway (test mode). No real payment is made.</p>
        <h1>{isCard ? "Bank card payment (Shetab)" : "Crypto payment"}</h1>
        <p>
          Amount:{" "}
          <strong data-testid="mock-amount">
            {isCard ? `${(amount / 10).toLocaleString("en-US")} toman (${amount.toLocaleString("en-US")} rial)` : `${amount} USDT`}
          </strong>
        </p>
        <p className="workspace-meta">Reference: {q.get("authority")}</p>
        <div className="billing-mock-actions">
          <button type="button" className="workspace-primary-button" data-testid="mock-pay" onClick={() => go(true)}>
            Pay
          </button>
          <button type="button" className="workspace-link-button" data-testid="mock-cancel" onClick={() => go(false)}>
            Cancel
          </button>
        </div>
      </section>
    </div>
  );
}

export default function MockPayPage() {
  return (
    <Suspense fallback={null}>
      <MockPay />
    </Suspense>
  );
}
