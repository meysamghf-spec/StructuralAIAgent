import { apiFetch } from "./api";
import { storeAuthSession } from "./auth-session";

export type UserResponse = {
  id: string;
  email: string;
  account_id: string;
  display_name: string | null;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  user: UserResponse;
};

export type FeatureAccessEntry = {
  available: boolean;
  reason: string;
  upgrade_product_id: string | null;
  product_name: string | null;
  entitlement_status: string | null;
  expires_at: string | null;
};

export type FeatureAccessSummary = {
  features: Record<string, FeatureAccessEntry>;
};

export async function registerUser(input: {
  email: string;
  password: string;
  display_name?: string;
}): Promise<AuthTokenResponse> {
  const response = await apiFetch<AuthTokenResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
  storeAuthSession(response.access_token, response.user.account_id);
  return response;
}

export async function loginUser(input: {
  email: string;
  password: string;
}): Promise<AuthTokenResponse> {
  const response = await apiFetch<AuthTokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
  storeAuthSession(response.access_token, response.user.account_id);
  return response;
}

export async function fetchCurrentUser(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/me");
}

export async function fetchFeatureAccess(): Promise<FeatureAccessSummary> {
  return apiFetch<FeatureAccessSummary>("/api/v1/auth/me/features");
}
