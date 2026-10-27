import { afterEach, describe, expect, it, vi } from "vitest";

const store: Record<string, string> = {};
vi.stubGlobal("window", {
  localStorage: {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => void (store[k] = v),
    removeItem: (k: string) => void delete store[k],
  },
});

import { completeGoogleSignIn, fetchGoogleSignInStatus, googleSignInStartUrl } from "../lib/auth-api";

function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => handler(String(url), init)));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.stubGlobal("window", { localStorage: { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => void (store[k] = v), removeItem: (k: string) => void delete store[k] } });
  for (const k of Object.keys(store)) delete store[k];
});

describe("google sign-in client", () => {
  it("builds the start URL with next and remember", () => {
    const url = googleSignInStartUrl("/projects?a=1", true);
    expect(url).toContain("/api/v1/auth/google/start?next=%2Fprojects%3Fa%3D1&remember=true");
    expect(googleSignInStartUrl("/", false)).toContain("remember=false");
  });

  it("shows the button only when the server says enabled", async () => {
    mockFetch(() => new Response(JSON.stringify({ enabled: true, reason: null }), { status: 200, headers: { "content-type": "application/json" } }));
    expect(await fetchGoogleSignInStatus()).toEqual({ enabled: true, reason: null });
    mockFetch(() => new Response(JSON.stringify({ enabled: false, reason: "ip_host" }), { status: 200, headers: { "content-type": "application/json" } }));
    expect(await fetchGoogleSignInStatus()).toEqual({ enabled: false, reason: "ip_host" });
    mockFetch(() => new Response("nope", { status: 500 }));
    expect(await fetchGoogleSignInStatus()).toEqual({ enabled: false, reason: null });
  });

  it("completes by trading the session cookie for a token and keeps the remember choice", async () => {
    const calls: string[] = [];
    mockFetch((url, init) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      return new Response(
        JSON.stringify({ access_token: "tok", token_type: "bearer", user: { id: "u", email: "a@b.co", account_id: "acc", display_name: null } }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    });
    const user = await completeGoogleSignIn(true);
    expect(user.email).toBe("a@b.co");
    expect(calls[0]).toMatch(/^POST .*\/api\/v1\/auth\/session$/);
    expect(store["structuralai.auth.token"]).toBe("tok");
    expect(store["structuralai.auth.remember"]).toBe("1");
    await completeGoogleSignIn(false);
    expect(store["structuralai.auth.remember"]).toBeUndefined();
  });

  it("fails clearly when the session cookie did not arrive", async () => {
    mockFetch(() => new Response(JSON.stringify({ error: { code: "AUTHENTICATION_ERROR", message: "No active session" } }), { status: 401, headers: { "content-type": "application/json" } }));
    await expect(completeGoogleSignIn(true)).rejects.toThrow();
  });
});
