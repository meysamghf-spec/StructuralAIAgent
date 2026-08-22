"use client";

import {
  createUpgradeInvoice,
  getUpgradeCatalog,
  listEntitlements,
  reconcilePayment,
  type EntitlementRecord,
  type PaymentInstructions,
  type UpgradeCatalog,
  type UpgradeProduct,
} from "@/lib/payments";
import {
  buildQrCodeUrl,
  formatCryptoAmount,
  formatFiatAmount,
  getPaymentProgressMessage,
  getPaymentStatusLabel,
} from "@/lib/upgrades-workspace";
import { useAuth } from "@/hooks/useAuth";
import { useCallback, useEffect, useState } from "react";

function badgeClass(status: string): string {
  if (status === "PAID" || status === "ACTIVE") return "status-pass";
  if (status === "FAILED" || status === "EXPIRED" || status === "UNDERPAID") return "status-error";
  if (status === "CONFIRMING" || status === "PAYMENT_DETECTED") return "status-warning";
  return "status-review";
}

export default function UpgradesWorkspaceClient() {
  const { features } = useAuth();
  const [catalog, setCatalog] = useState<UpgradeCatalog | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<UpgradeProduct | null>(null);
  const [currency, setCurrency] = useState("BTC");
  const [network, setNetwork] = useState("bitcoin");
  const [invoice, setInvoice] = useState<PaymentInstructions | null>(null);
  const [paymentStatus, setPaymentStatus] = useState<string>("");
  const [confirmations, setConfirmations] = useState(0);
  const [upgradeActivated, setUpgradeActivated] = useState(false);
  const [entitlements, setEntitlements] = useState<EntitlementRecord[]>([]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const loadCatalog = useCallback(async () => {
    const [catalogData, entitlementData] = await Promise.all([getUpgradeCatalog(), listEntitlements()]);
    setCatalog(catalogData);
    setSelectedProduct(catalogData.products[0] ?? null);
    setEntitlements(entitlementData);
    if (catalogData.supported_crypto[0]) {
      setCurrency(catalogData.supported_crypto[0].currency);
      setNetwork(catalogData.supported_crypto[0].network);
    }
  }, []);

  useEffect(() => {
    void loadCatalog().catch((err) => {
      setError(err instanceof Error ? err.message : "Failed to load upgrade catalog");
    });
  }, [loadCatalog]);

  async function handleCreateInvoice() {
    if (!selectedProduct) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const created = await createUpgradeInvoice({
        upgrade_product_id: selectedProduct.id,
        currency,
        network,
        idempotency_key: `ui-${selectedProduct.id}-${currency}-${Date.now()}`,
      });
      setInvoice(created);
      setPaymentStatus(created.payment.status);
      setConfirmations(created.payment.current_confirmations);
      setUpgradeActivated(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create invoice");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshStatus() {
    if (!invoice) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await reconcilePayment(invoice.payment.id);
      setPaymentStatus(result.payment.status);
      setConfirmations(result.payment.current_confirmations);
      setUpgradeActivated(result.upgrade_activated);
      setInvoice({
        ...invoice,
        payment: result.payment,
      });
      const entitlementData = await listEntitlements();
      setEntitlements(entitlementData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh payment status");
    } finally {
      setLoading(false);
    }
  }

  const qrUrl = buildQrCodeUrl(invoice?.payment.payment_uri);
  const requiredConfirmations = invoice?.payment.required_confirmations ?? 3;

  return (
    <div className="workspace-page">
      <section className="workspace-card">
        <h1>Upgrade with Digital Currency</h1>
        <p className="workspace-help">
          Purchase product upgrades using supported cryptocurrencies. Payments are verified server-side
          before your upgrade is activated. Never share private keys or seed phrases.
        </p>
      </section>

      {error ? <p className="workspace-error">{error}</p> : null}

      {features ? (
        <section className="workspace-card">
          <h2>Your feature access</h2>
          <p className="workspace-help">
            Feature availability is determined by the backend entitlement service.
          </p>
          <ul className="workspace-list">
            {Object.entries(features.features).map(([key, entry]) => (
              <li key={key}>
                <strong>{key}</strong>: {entry.available ? "Available" : entry.reason}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="workspace-card-grid">
        {catalog?.products.map((product) => (
          <article
            key={product.id}
            className={selectedProduct?.id === product.id ? "workspace-card selected-card" : "workspace-card"}
          >
            <button type="button" className="workspace-link-button" onClick={() => setSelectedProduct(product)}>
              <strong>{product.name}</strong>
              <span>{formatFiatAmount(product.fiat_price_usd)}</span>
              <span className="workspace-meta">{product.description}</span>
              <ul className="workspace-list">
                {product.features.slice(0, 3).map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
            </button>
          </article>
        ))}
      </section>

      {selectedProduct ? (
        <section className="workspace-card">
          <h2>Create payment invoice</h2>
          <div className="workspace-form-row">
            <label htmlFor="currency-select">Currency</label>
            <select
              id="currency-select"
              value={`${currency}:${network}`}
              onChange={(event) => {
                const [nextCurrency, nextNetwork] = event.target.value.split(":");
                setCurrency(nextCurrency);
                setNetwork(nextNetwork);
              }}
            >
              {catalog?.supported_crypto.map((option) => (
                <option key={`${option.currency}:${option.network}`} value={`${option.currency}:${option.network}`}>
                  {option.display_name} ({option.network})
                </option>
              ))}
            </select>
          </div>
          <p>
            Selected upgrade: <strong>{selectedProduct.name}</strong> — {formatFiatAmount(selectedProduct.fiat_price_usd)}
          </p>
          <button type="button" className="workspace-primary-button" disabled={loading} onClick={() => void handleCreateInvoice()}>
            Create invoice
          </button>
        </section>
      ) : null}

      {invoice ? (
        <section className="workspace-card">
          <h2>Payment instructions</h2>
          <p>
            Status:{" "}
            <span className={badgeClass(paymentStatus)}>{getPaymentStatusLabel(paymentStatus)}</span>
          </p>
          <p>{getPaymentProgressMessage(paymentStatus, confirmations, requiredConfirmations)}</p>
          <p>Send exactly {formatCryptoAmount(invoice.payment.crypto_amount, invoice.payment.currency)}</p>
          <p className="workspace-meta">Network: {invoice.payment.network}</p>
          <p className="workspace-meta">Payment address: {invoice.payment.payment_address}</p>
          <p className="workspace-meta">Invoice expires: {new Date(invoice.payment.expires_at).toLocaleString()}</p>
          {invoice.payment.payment_uri ? (
            <p className="workspace-meta">Payment URI: {invoice.payment.payment_uri}</p>
          ) : null}
          {qrUrl ? (
            <p>
              <img src={qrUrl} alt="Payment QR code" width={180} height={180} />
            </p>
          ) : null}
          {upgradeActivated ? (
            <p className="status-pass">Upgrade activated after verified payment.</p>
          ) : (
            <button type="button" className="workspace-link-button" disabled={loading} onClick={() => void handleRefreshStatus()}>
              Check payment status
            </button>
          )}
        </section>
      ) : null}

      <section className="workspace-card">
        <h2>Your entitlements</h2>
        {entitlements.length === 0 ? (
          <p className="workspace-help">No active upgrades yet. Complete a verified payment to activate an entitlement.</p>
        ) : (
          <ul className="workspace-list">
            {entitlements.map((item) => (
              <li key={item.id}>
                {item.upgrade_product_id} — <span className={badgeClass(item.status)}>{item.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
