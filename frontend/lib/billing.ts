import { apiFetch } from "./api";

export type Limits = {
  projects: number | null;
  analyses_per_month: number | null;
  frame_max_storeys: number | null;
  frame_max_bays: number | null;
  design_sheets: string[];
  exports: string[];
  autocad_imports_per_month: number | null;
  optimization: boolean;
  seats: number | null;
  storage_mb: number | null;
  support: string;
};
export type Plan = {
  id: string;
  name: string;
  name_fa?: string;
  tagline?: string;
  tagline_fa?: string;
  price_toman: number;
  price_usdt: number;
  purchasable: boolean;
  highlight?: boolean;
  limits: Limits;
  features?: string[];
  quotes?: Record<string, Quote>;
};
export type Quote = {
  plan_id: string;
  duration_id: string;
  months: number;
  discount_pct: number;
  amount_toman: number;
  amount_usdt: number;
  list_toman: number;
  list_usdt: number;
};
export type Duration = { id: string; label: string; label_fa?: string; months: number; discount_pct: number };
export type Catalog = {
  plans: Plan[];
  durations: Duration[];
  currency_note?: string;
  assets: CryptoAsset[];
  invoice_minutes: number;
};
export type CryptoAsset = {
  id: string;
  coin: string;
  network: string;
  standard: string;
  stable: boolean;
  optional: boolean;
  live: boolean;
  contract: string;
  processor: string;
  available?: boolean;
  decimals?: number;
  chain?: string;
  chain_id?: number | null;
  address?: string;
  explorer?: string;
  confirmations?: number | null;
};
export type Invoice = {
  id: string;
  number: string;
  plan_id: string;
  plan_name: string;
  duration_id: string;
  months: number;
  method: "crypto";
  gateway: string;
  mock: boolean;
  asset_id: string;
  coin: string;
  network: string;
  standard: string;
  amount_crypto: string;
  rate_usd: number | null;
  rate_source: string;
  pay_address: string;
  payment_uri?: string;
  checkout_url?: string;
  qr_svg?: string;
  amount_toman: number;
  amount_usdt: number;
  status: "pending" | "paid" | "failed" | "expired" | "cancelled";
  created_at: string;
  expires_at: string;
  paid_at: string | null;
  ref_id: string;
  tx?: string;
  contract?: string;
  qr_address_svg?: string;
  chain_id?: number;
  explorer?: string;
  confirmations_required?: number;
  auto_detect?: boolean;
  window_open?: boolean;
  detected?: { tx: string; block: number; confirmations: number; required: number };
  underpaid?: { tx: string; received: string; missing: string };
  paid_via?: string;
  paid_late?: boolean;
  received?: string;
};
export type Subscription = { plan_id: string; plan_name: string; started_at: string; expires_at: string; last_invoice: string };
export type BillingAccount = {
  plan: Plan;
  subscription: Subscription | null;
  complimentary: boolean;
  usage: { analyses_per_month: number; autocad_imports_per_month: number };
  invoices: Invoice[];
  history: { at: string; action: string; plan_id: string; invoice: string; expires_at: string }[];
  payments: { methods: string[]; mock: boolean; live_assets: string[]; btcpay: boolean; mock_allowed?: boolean };
  enforcement: boolean;
};

export const getBillingPlans = () => apiFetch<Catalog>("/api/v1/billing/plans");
export const getBillingAccount = () => apiFetch<BillingAccount>("/api/v1/billing/account");
export const startCheckout = (plan_id: string, duration_id: string, asset_id: string) =>
  apiFetch<{ invoice: Invoice }>("/api/v1/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ plan_id, duration_id, asset_id }),
  });
export const getInvoice = (id: string) => apiFetch<{ invoice: Invoice }>(`/api/v1/billing/invoices/${id}`);
export const mockConfirmInvoice = (id: string, ok: boolean) =>
  apiFetch<{ invoice: Invoice }>(`/api/v1/billing/invoices/${id}/mock-confirm`, {
    method: "POST",
    body: JSON.stringify({ ok }),
  });

export const claimInvoiceTx = (id: string, tx: string) =>
  apiFetch<{ invoice: Invoice }>(`/api/v1/billing/invoices/${id}/claim-tx`, {
    method: "POST",
    body: JSON.stringify({ tx }),
  });

export function fmtToman(n: number): string {
  return `${Math.round(n).toLocaleString("en-US")} toman`;
}
export function fmtLimit(v: number | null | undefined, unit = ""): string {
  if (v === null || v === undefined) return "Unlimited";
  return `${v.toLocaleString("en-US")}${unit}`;
}
export function fmtStorage(mb: number | null): string {
  if (mb === null) return "Unlimited";
  return mb >= 1000 ? `${(mb / 1000).toLocaleString("en-US")} GB` : `${mb} MB`;
}
