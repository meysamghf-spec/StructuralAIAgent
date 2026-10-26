import { apiFetch, getApiBaseUrl } from "./api";
import { setRememberHint, storeAuthSession } from "./auth-session";

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
    credentials: "include",
  });
  storeAuthSession(response.access_token, response.user.account_id);
  return response;
}

export async function loginUser(input: {
  email: string;
  password: string;
  remember_me?: boolean;
}): Promise<AuthTokenResponse> {
  const response = await apiFetch<AuthTokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
    credentials: "include", // accept the httpOnly session cookie
  });
  storeAuthSession(response.access_token, response.user.account_id);
  setRememberHint(Boolean(input.remember_me));
  return response;
}

/** Trade the httpOnly "remember me" cookie for a bearer token (null when there is no live session). */
export async function restoreSession(): Promise<AuthTokenResponse | null> {
  try {
    const response = await apiFetch<AuthTokenResponse>("/api/v1/auth/session", { method: "POST", credentials: "include" });
    storeAuthSession(response.access_token, response.user.account_id);
    return response;
  } catch {
    return null;
  }
}

export async function logoutRemote(): Promise<void> {
  try {
    await apiFetch<void>("/api/v1/auth/logout", { method: "POST", credentials: "include" });
  } catch {
    /* the local session is cleared regardless */
  }
}

export async function fetchCurrentUser(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/me");
}

export async function fetchFeatureAccess(): Promise<FeatureAccessSummary> {
  return apiFetch<FeatureAccessSummary>("/api/v1/auth/me/features");
}

export async function fetchGoogleSignInEnabled(): Promise<boolean> {
  try {
    const res = await apiFetch<{ enabled: boolean }>("/api/v1/auth/google/config");
    return Boolean(res.enabled);
  } catch {
    return false;
  }
}

export function googleSignInStartUrl(nextPath: string): string {
  return `${getApiBaseUrl()}/api/v1/auth/google/start?next=${encodeURIComponent(nextPath)}`;
}

/** Finish a Google sign-in redirect: store the token from the URL fragment and resolve the account. */
export async function completeGoogleSignIn(token: string): Promise<UserResponse> {
  storeAuthSession(token, "");
  const me = await fetchCurrentUser();
  storeAuthSession(token, me.account_id);
  return me;
}
