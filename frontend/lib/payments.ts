import { apiFetch } from "./api";

export type UpgradeProduct = {
  id: string;
  name: string;
  description: string;
  fiat_price_usd: number;
  billing_period_days: number | null;
  features: string[];
};

export type SupportedCrypto = {
  currency: string;
  network: string;
  display_name: string;
  required_confirmations: number;
  decimals: number;
};

export type PaymentRecord = {
  id: string;
  upgrade_product_id: string;
  invoice_id: string;
  currency: string;
  network: string;
  fiat_amount_usd: number;
  crypto_amount: number;
  received_amount: number | null;
  payment_address: string;
  payment_uri: string | null;
  transaction_hash: string | null;
  required_confirmations: number;
  current_confirmations: number;
  status: string;
  expires_at: string;
  exchange_rate: number | null;
  exchange_rate_source: string | null;
};

export type PaymentInstructions = {
  payment: PaymentRecord;
  instructions: Record<string, unknown>;
};

export type PaymentStatusPayload = {
  payment: PaymentRecord;
  entitlement: Record<string, unknown> | null;
  upgrade_activated: boolean;
};

export type EntitlementRecord = {
  id: string;
  upgrade_product_id: string;
  status: string;
  activated_at: string | null;
  expires_at: string | null;
};

export type UpgradeCatalog = {
  products: UpgradeProduct[];
  supported_crypto: SupportedCrypto[];
};

export async function getUpgradeCatalog(): Promise<UpgradeCatalog> {
  return apiFetch<UpgradeCatalog>("/api/v1/payments/catalog");
}

export async function createUpgradeInvoice(input: {
  upgrade_product_id: string;
  currency: string;
  network: string;
  idempotency_key?: string;
}): Promise<PaymentInstructions> {
  return apiFetch<PaymentInstructions>("/api/v1/payments/invoices", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getPaymentStatus(paymentId: string): Promise<PaymentStatusPayload> {
  return apiFetch<PaymentStatusPayload>(`/api/v1/payments/invoices/${paymentId}`);
}

export async function reconcilePayment(paymentId: string): Promise<PaymentStatusPayload> {
  return apiFetch<PaymentStatusPayload>(`/api/v1/payments/invoices/${paymentId}/reconcile`, {
    method: "POST",
  });
}

export async function listEntitlements(): Promise<EntitlementRecord[]> {
  return apiFetch<EntitlementRecord[]>("/api/v1/payments/entitlements");
}
