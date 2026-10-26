import { getBillingAccount } from "./billing";

export type DetailingPlan = { designSheets: string[] | null; enforcement: boolean };

let cache: { at: number; value: Promise<DetailingPlan> } | null = null;

/** The account's plan gate for rebar sheets (cached for a minute). Guests / failures -> unrestricted view; the backend still enforces. */
export function loadDetailingPlan(now: number = Date.now()): Promise<DetailingPlan> {
  if (cache && now - cache.at < 60_000) return cache.value;
  const value = getBillingAccount()
    .then((a): DetailingPlan => ({ designSheets: a.plan?.limits?.design_sheets ?? null, enforcement: a.enforcement !== false }))
    .catch((): DetailingPlan => ({ designSheets: null, enforcement: false }));
  cache = { at: now, value };
  return value;
}

export function resetDetailingPlanCache(): void {
  cache = null;
}
