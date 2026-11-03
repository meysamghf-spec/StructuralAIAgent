import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { bootstrapAuth, isSessionRejected } from "@/lib/auth-bootstrap";

function deps(over: Partial<Parameters<typeof bootstrapAuth>[0]> = {}) {
  return {
    getToken: () => "tok",
    hasRememberHint: () => false,
    restoreSession: vi.fn(async () => null),
    fetchCurrentUser: vi.fn(async () => ({ id: "u1" })),
    clearSession: vi.fn(),
    retryDelayMs: 0,
    ...over,
  };
}

describe("bootstrapAuth (mobile session drop)", () => {
  it("authenticates with a stored token", async () => {
    const d = deps();
    expect(await bootstrapAuth(d)).toEqual({ status: "authenticated", user: { id: "u1" } });
    expect(d.clearSession).not.toHaveBeenCalled();
  });

  it("keeps the token when the request is aborted by a page navigation", async () => {
    const d = deps({
      fetchCurrentUser: vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
      isUnloading: () => true,
    });
    expect((await bootstrapAuth(d)).status).toBe("unavailable");
    expect(d.clearSession).not.toHaveBeenCalled();
  });

  it("keeps the token on network errors / 5xx and retries once", async () => {
    const me = vi
      .fn()
      .mockRejectedValueOnce(new ApiError("bad gateway", 502, null, {}, null))
      .mockResolvedValueOnce({ id: "u1" });
    const d = deps({ fetchCurrentUser: me });
    expect((await bootstrapAuth(d)).status).toBe("authenticated");
    expect(me).toHaveBeenCalledTimes(2);
    expect(d.clearSession).not.toHaveBeenCalled();
  });

  it("does not sign out when the API stays unreachable", async () => {
    const d = deps({ fetchCurrentUser: vi.fn(async () => Promise.reject(new TypeError("offline"))) });
    expect((await bootstrapAuth(d)).status).toBe("unavailable");
    expect(d.clearSession).not.toHaveBeenCalled();
  });

  it("signs out only when the API rejects the token", async () => {
    const d = deps({ fetchCurrentUser: vi.fn(async () => Promise.reject(new ApiError("expired", 401, null, {}, null))) });
    expect((await bootstrapAuth(d)).status).toBe("anonymous");
    expect(d.clearSession).toHaveBeenCalledTimes(1);
  });

  it("does not clear on 401 while the page unloads", async () => {
    const d = deps({
      fetchCurrentUser: vi.fn(async () => Promise.reject(new ApiError("x", 401, null, {}, null))),
      isUnloading: () => true,
    });
    await bootstrapAuth(d);
    expect(d.clearSession).not.toHaveBeenCalled();
  });

  it("restores a remembered session when no token is stored", async () => {
    let token: string | null = null;
    const d = deps({
      getToken: () => token,
      hasRememberHint: () => true,
      restoreSession: vi.fn(async () => {
        token = "t";
      }),
    });
    expect((await bootstrapAuth(d)).status).toBe("authenticated");
  });

  it("is anonymous without a token or remember hint", async () => {
    const d = deps({ getToken: () => null });
    expect((await bootstrapAuth(d)).status).toBe("anonymous");
    expect(d.fetchCurrentUser).not.toHaveBeenCalled();
  });

  it("classifies only 401/403 as session rejection", () => {
    expect(isSessionRejected(new ApiError("", 401, null, {}, null))).toBe(true);
    expect(isSessionRejected(new ApiError("", 500, null, {}, null))).toBe(false);
    expect(isSessionRejected(new DOMException("aborted", "AbortError"))).toBe(false);
  });
});
