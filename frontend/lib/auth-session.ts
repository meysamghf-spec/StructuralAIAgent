/** Auth session helpers for the frontend. */

const AUTH_TOKEN_KEY = "structuralai.auth.token";
const AUTH_ACCOUNT_KEY = "structuralai.auth.accountId";

export function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getStoredAccountId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_ACCOUNT_KEY);
}

export function storeAuthSession(accessToken: string, accountId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, accessToken);
  window.localStorage.setItem(AUTH_ACCOUNT_KEY, accountId);
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_ACCOUNT_KEY);
}

export function hasStoredAuthToken(): boolean {
  return getStoredAuthToken() !== null;
}

export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getStoredAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export function getUploadAuthHeaders(): Record<string, string> {
  return getAuthHeaders();
}
