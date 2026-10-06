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

describe("register page modules", () => {
  it("loads register page and client components", async () => {
    const page = await import("../app/register/page");
    const client = await import("../app/register/RegisterClient");
    expect(page.default).toBeTypeOf("function");
    expect(client.default).toBeTypeOf("function");
  });

  it("defines required register page copy and fields", async () => {
    const { REGISTER_PAGE } = await import("../lib/auth-forms");
    expect(REGISTER_PAGE.eyebrow).toBe("Sign up");
    expect(REGISTER_PAGE.heading).toBe("Create your account");
    expect(REGISTER_PAGE.fields).toEqual([
      "displayName",
      "email",
      "password",
      "confirmPassword",
    ]);
    expect(REGISTER_PAGE.submitIdle).toBe("Create account");
  });
});

describe("registration form validation", () => {
  it("requires email and password", async () => {
    const { validateRegistrationForm } = await import("../lib/auth-forms");
    const result = validateRegistrationForm({
      email: "",
      password: "",
      confirmPassword: "",
      displayName: "",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.fieldErrors.email).toBe("Email is required.");
      expect(result.fieldErrors.password).toBe("Password is required.");
      expect(result.fieldErrors.confirmPassword).toBe("Please confirm your password.");
    }
  });

  it("rejects invalid email", async () => {
    const { validateRegistrationForm } = await import("../lib/auth-forms");
    const result = validateRegistrationForm({
      email: "not-an-email",
      password: "secure-password",
      confirmPassword: "secure-password",
      displayName: "",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.fieldErrors.email).toBe("Enter a valid email address.");
    }
  });

  it("rejects password mismatch", async () => {
    const { validateRegistrationForm } = await import("../lib/auth-forms");
    const result = validateRegistrationForm({
      email: "engineer@example.com",
      password: "secure-password",
      confirmPassword: "different-password",
      displayName: "",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.fieldErrors.confirmPassword).toBe("Passwords do not match.");
    }
  });

  it("allows optional display name", async () => {
    const { validateRegistrationForm } = await import("../lib/auth-forms");
    const withoutName = validateRegistrationForm({
      email: "engineer@example.com",
      password: "secure-password",
      confirmPassword: "secure-password",
      displayName: "   ",
    });
    expect(withoutName.ok).toBe(true);
    if (withoutName.ok) {
      expect(withoutName.displayName).toBeUndefined();
    }

    const withName = validateRegistrationForm({
      email: "engineer@example.com",
      password: "secure-password",
      confirmPassword: "secure-password",
      displayName: "  Alex Engineer  ",
    });
    expect(withName.ok).toBe(true);
    if (withName.ok) {
      expect(withName.displayName).toBe("Alex Engineer");
    }
  });

  it("trims email on success", async () => {
    const { validateRegistrationForm } = await import("../lib/auth-forms");
    const result = validateRegistrationForm({
      email: "  engineer@example.com  ",
      password: "secure-password",
      confirmPassword: "secure-password",
      displayName: "",
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.email).toBe("engineer@example.com");
    }
  });
});

describe("registration navigation links", () => {
  it("login page links to register with required copy", async () => {
    const { AUTH_NAV_LINKS } = await import("../lib/auth-forms");
    expect(AUTH_NAV_LINKS.signInToSignUp.prompt).toBe("Don't have an account?");
    expect(AUTH_NAV_LINKS.signInToSignUp.label).toBe("Sign up");
    expect(AUTH_NAV_LINKS.signInToSignUp.href).toBe("/register");
    expect(
      `${AUTH_NAV_LINKS.signInToSignUp.prompt} ${AUTH_NAV_LINKS.signInToSignUp.label}`,
    ).toBe("Don't have an account? Sign up");
  });

  it("register page links to login with required copy", async () => {
    const { AUTH_NAV_LINKS } = await import("../lib/auth-forms");
    expect(AUTH_NAV_LINKS.signUpToSignIn.prompt).toBe("Already have an account?");
    expect(AUTH_NAV_LINKS.signUpToSignIn.label).toBe("Sign in");
    expect(AUTH_NAV_LINKS.signUpToSignIn.href).toBe("/login");
    expect(
      `${AUTH_NAV_LINKS.signUpToSignIn.prompt} ${AUTH_NAV_LINKS.signUpToSignIn.label}`,
    ).toBe("Already have an account? Sign in");
  });

  it("routes successful registration to the dashboard", async () => {
    const { AUTH_ROUTES } = await import("../lib/auth-forms");
    expect(AUTH_ROUTES.dashboard).toBe("/");
  });
});

describe("registration error formatting", () => {
  it("maps network failures to a friendly message", async () => {
    const { formatRegistrationError } = await import("../lib/auth-forms");
    expect(formatRegistrationError(new Error("Failed to fetch"))).toBe(
      "Unable to reach the server. Check your connection and try again.",
    );
  });

  it("surfaces email already registered from backend", async () => {
    const { formatRegistrationError } = await import("../lib/auth-forms");
    expect(
      formatRegistrationError(new Error("A user with this email already exists")),
    ).toBe("A user with this email already exists");
  });

  it("surfaces invalid email from backend", async () => {
    const { formatRegistrationError } = await import("../lib/auth-forms");
    expect(formatRegistrationError(new Error("Email address is invalid"))).toBe(
      "Email address is invalid",
    );
  });

  it("surfaces invalid password from backend", async () => {
    const { formatRegistrationError } = await import("../lib/auth-forms");
    expect(
      formatRegistrationError(new Error("Password must be at least 8 characters")),
    ).toBe("Password must be at least 8 characters");
  });

  it("hides internal stack traces and unexpected errors", async () => {
    const { formatRegistrationError } = await import("../lib/auth-forms");
    expect(
      formatRegistrationError(new Error("SyntaxError: Unexpected token < in JSON")),
    ).toBe("Registration failed. Please try again.");
    expect(formatRegistrationError("not an error")).toBe(
      "An unexpected error occurred. Please try again.",
    );
    expect(formatRegistrationError(new Error(""))).toBe(
      "Registration failed. Please try again.",
    );
  });

  it("maps generic API failures without leaking status details", async () => {
    const { formatRegistrationError } = await import("../lib/auth-forms");
    expect(formatRegistrationError(new Error("Request failed (500)"))).toBe(
      "Registration failed. Please try again.",
    );
  });
});

describe("registration submit flow", () => {
  beforeEach(() => {
    Object.keys(storage).forEach((key) => delete storage[key]);
    installBrowserStorage();
    vi.resetModules();
  });

  it("registerUser stores token and account_id on success", async () => {
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
            display_name: "Alex",
          },
        }),
      })),
    );

    const { validateRegistrationForm } = await import("../lib/auth-forms");
    const validation = validateRegistrationForm({
      email: "new@example.com",
      password: "secure-password",
      confirmPassword: "secure-password",
      displayName: "Alex",
    });
    expect(validation.ok).toBe(true);
    if (!validation.ok) {
      throw new Error("expected valid registration input");
    }

    const { registerUser } = await import("../lib/auth-api");
    const response = await registerUser({
      email: validation.email,
      password: validation.password,
      display_name: validation.displayName,
    });

    expect(response.access_token).toBe("jwt-register-token");
    expect(response.user.account_id).toBe("acct-new");

    const session = await import("../lib/auth-session");
    expect(session.getStoredAuthToken()).toBe("jwt-register-token");
    expect(session.getStoredAccountId()).toBe("acct-new");
  });

  it("registerUser rejects duplicate email registration", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({
          error: { message: "A user with this email already exists" },
        }),
      })),
    );

    const { registerUser } = await import("../lib/auth-api");
    await expect(
      registerUser({ email: "dup@example.com", password: "secure-password" }),
    ).rejects.toThrow("A user with this email already exists");
  });

  it("validated registration followed by token storage enters authenticated session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          access_token: "jwt-after-register",
          token_type: "bearer",
          user: {
            id: "user-id",
            email: "signup@example.com",
            account_id: "acct-signup",
            display_name: null,
          },
        }),
      })),
    );

    const { validateRegistrationForm, AUTH_ROUTES } = await import("../lib/auth-forms");
    const validation = validateRegistrationForm({
      email: "signup@example.com",
      password: "secure-password",
      confirmPassword: "secure-password",
      displayName: "",
    });
    expect(validation.ok).toBe(true);
    if (!validation.ok) {
      throw new Error("expected valid registration input");
    }

    const { registerUser } = await import("../lib/auth-api");
    await registerUser({
      email: validation.email,
      password: validation.password,
    });

    const session = await import("../lib/auth-session");
    expect(session.hasStoredAuthToken()).toBe(true);
    expect(AUTH_ROUTES.dashboard).toBe("/");
  });
});
