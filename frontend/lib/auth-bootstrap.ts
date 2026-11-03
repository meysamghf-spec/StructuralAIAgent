/** Startup session check for AuthProvider, kept framework-free so it can be unit tested.
 *
 *  Mobile bug (fix/mobile-session-drop): the old bootstrap wiped the stored token on ANY error. When the user
 *  navigated to another page while /auth/me or /auth/me/features was still in flight (slow mobile network),
 *  the browser aborted the fetch (nginx logs 499), the rejected promise hit the catch-all and called
 *  clearAuthSession() just before the page unloaded. The next page found no token and redirected to /login.
 *  Now only a real rejection of the session by the API (401/403) signs the user out; network errors, aborts,
 *  timeouts and 5xx keep the token, and feature access is loaded separately so it can never block or sign out.
 */
import { ApiError } from "./api";

export function isSessionRejected(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export type BootstrapDeps<U> = {
  getToken: () => string | null;
  hasRememberHint: () => boolean;
  restoreSession: () => Promise<unknown>;
  fetchCurrentUser: () => Promise<U>;
  clearSession: () => void;
  /** True once the page is being unloaded: errors then come from aborted requests and must be ignored. */
  isUnloading?: () => boolean;
  retryDelayMs?: number;
};

export type BootstrapResult<U> =
  | { status: "authenticated"; user: U }
  | { status: "anonymous" }
  | { status: "unavailable" }; // could not reach the API: token kept, user unknown

export async function bootstrapAuth<U>(deps: BootstrapDeps<U>): Promise<BootstrapResult<U>> {
  if (!deps.getToken() && deps.hasRememberHint()) {
    try {
      await deps.restoreSession();
    } catch {
      /* no remembered session */
    }
  }
  if (!deps.getToken()) return { status: "anonymous" };

  let lastError: unknown = null;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      return { status: "authenticated", user: await deps.fetchCurrentUser() };
    } catch (error) {
      lastError = error;
      if (deps.isUnloading?.()) return { status: "unavailable" };
      if (isSessionRejected(error)) break;
      if (attempt === 0) await new Promise((r) => setTimeout(r, deps.retryDelayMs ?? 800));
    }
  }
  if (isSessionRejected(lastError) && !deps.isUnloading?.()) {
    deps.clearSession();
    return { status: "anonymous" };
  }
  return { status: "unavailable" };
}
