import { beforeEach, describe, expect, it, vi } from "vitest";

const storage: Record<string, string> = {};

function installBrowserStorage() {
  const localStorageMock = {
    getItem: (key: string) => storage[key] ?? null,
    setItem: (key: string, value: string) => {
      storage[key] = value;
    },
    removeItem: (key: string) => {
      delete storage[key];
    },
  };
  vi.stubGlobal("window", { localStorage: localStorageMock });
  vi.stubGlobal("localStorage", localStorageMock);
}

describe("auth session", () => {
  beforeEach(() => {
    Object.keys(storage).forEach((key) => delete storage[key]);
    installBrowserStorage();
    vi.resetModules();
  });

  it("stores and clears authenticated session", async () => {
    const session = await import("../lib/auth-session");
    session.storeAuthSession("token-123", "account-abc");
    expect(session.getStoredAuthToken()).toBe("token-123");
    expect(session.getStoredAccountId()).toBe("account-abc");
    expect(session.hasStoredAuthToken()).toBe(true);
    expect(session.getAuthHeaders()).toEqual({ Authorization: "Bearer token-123" });

    session.clearAuthSession();
    expect(session.getStoredAuthToken()).toBeNull();
    expect(session.getAuthHeaders()).toEqual({});
  });

  it("does not emit fake X-Actor-Id headers when unauthenticated", async () => {
    const session = await import("../lib/auth-session");
    expect(session.getAuthHeaders()).toEqual({});
    expect(session.getUploadAuthHeaders()).toEqual({});
  });
});

describe("auth api integration", () => {
  beforeEach(() => {
    Object.keys(storage).forEach((key) => delete storage[key]);
    installBrowserStorage();
    vi.resetModules();
  });

  it("login success stores bearer token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          access_token: "jwt-login-token",
          token_type: "bearer",
          user: {
            id: "user-id",
            email: "engineer@example.com",
            account_id: "acct-1",
            display_name: "Engineer",
          },
        }),
      })),
    );

    const authApi = await import("../lib/auth-api");
    const response = await authApi.loginUser({
      email: "engineer@example.com",
      password: "secure-password",
    });

    expect(response.access_token).toBe("jwt-login-token");
    const session = await import("../lib/auth-session");
    expect(session.getStoredAuthToken()).toBe("jwt-login-token");
  });

  it("login failure surfaces backend error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 401,
        json: async () => ({
          error: { message: "Invalid email or password" },
        }),
      })),
    );

    const { loginUser } = await import("../lib/auth-api");
    await expect(
      loginUser({ email: "bad@example.com", password: "wrong-password" }),
    ).rejects.toThrow("Invalid email or password");
  });

  it("registration success stores bearer token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          access_token: "jwt-register-token",
          token_type: "bearer",
          user: {
            id: "user-id",
            email: "new@example.com",
            account_id: "acct-new",
            display_name: null,
          },
        }),
      })),
    );

    const { registerUser } = await import("../lib/auth-api");
    await registerUser({
      email: "new@example.com",
      password: "secure-password",
    });

    const session = await import("../lib/auth-session");
    expect(session.getStoredAuthToken()).toBe("jwt-register-token");
  });

  it("registration failure surfaces backend error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({
          error: { message: "Email already registered" },
        }),
      })),
    );

    const { registerUser } = await import("../lib/auth-api");
    await expect(
      registerUser({ email: "dup@example.com", password: "secure-password" }),
    ).rejects.toThrow("Email already registered");
  });
});

describe("api authentication headers", () => {
  beforeEach(() => {
    Object.keys(storage).forEach((key) => delete storage[key]);
    installBrowserStorage();
    vi.resetModules();
  });

  it("authenticated apiFetch includes Bearer token", async () => {
    const session = await import("../lib/auth-session");
    session.storeAuthSession("jwt-api-token", "acct-1");

    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ projects: [] }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { apiFetch } = await import("../lib/api");
    await apiFetch("/api/v1/projects");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({
      Authorization: "Bearer jwt-api-token",
      "Content-Type": "application/json",
    });
    expect(JSON.stringify(init.headers)).not.toContain("X-Actor-Id");
  });

  it("unauthenticated apiFetch does not use fake X-Actor-Id", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ status: "ok" }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { apiFetch } = await import("../lib/api");
    await apiFetch("/health");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.stringify(init.headers)).not.toContain("X-Actor-Id");
    expect(JSON.stringify(init.headers)).not.toContain("workspace-user");
  });

  it("file upload includes Bearer token without manual Content-Type", async () => {
    const session = await import("../lib/auth-session");
    session.storeAuthSession("jwt-upload-token", "acct-1");

    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        id: "file-id",
        filename: "drawing.pdf",
        file_type: "pdf",
        parsing_status: "PENDING",
        extraction_status: "PENDING",
        upload_time: "2026-01-01T00:00:00Z",
        created_at: "2026-01-01T00:00:00Z",
      }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { uploadProjectFile } = await import("../lib/api");
    const file = new File(["content"], "drawing.pdf", { type: "application/pdf" });
    await uploadProjectFile("project-id", file);

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.headers).toEqual({ Authorization: "Bearer jwt-upload-token" });
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("fetchCurrentUser reads backend-authoritative feature state endpoint", async () => {
    const session = await import("../lib/auth-session");
    session.storeAuthSession("jwt-me-token", "acct-1");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "user-id",
          email: "engineer@example.com",
          account_id: "acct-1",
          display_name: "Engineer",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          features: {
            CAD_GENERATION: {
              available: false,
              reason: "Upgrade required",
              upgrade_product_id: "cad-pro",
              product_name: "CAD Pro",
              entitlement_status: null,
              expires_at: null,
            },
          },
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const { fetchCurrentUser, fetchFeatureAccess } = await import("../lib/auth-api");
    const user = await fetchCurrentUser();
    const features = await fetchFeatureAccess();

    expect(user.email).toBe("engineer@example.com");
    expect(features.features.CAD_GENERATION.available).toBe(false);
    expect(features.features.CAD_GENERATION.reason).toBe("Upgrade required");
  });
});
