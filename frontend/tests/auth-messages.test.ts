import { describe, expect, it } from "vitest";
import { ApiError } from "../lib/api";
import { classifyLoginError, loginErrorMessage, validateLoginInput } from "../lib/auth-messages";

const api = (code: string, status = 401, details = {}, retry: number | null = null) =>
  new ApiError("m", status, code, details, retry);

describe("login errors", () => {
  it("classifies every reason", () => {
    expect(classifyLoginError(api("EMAIL_NOT_REGISTERED")).kind).toBe("not_registered");
    expect(classifyLoginError(api("WRONG_PASSWORD", 401, { attempts_left: 2 }))).toMatchObject({ kind: "wrong_password", attemptsLeft: 2 });
    expect(classifyLoginError(api("INVALID_EMAIL", 422)).kind).toBe("invalid_email");
    expect(classifyLoginError(api("RATE_LIMITED", 429, {}, 600))).toMatchObject({ kind: "rate_limited", retryAfterSeconds: 600 });
    expect(classifyLoginError(api("ACCOUNT_DISABLED", 403)).kind).toBe("disabled");
    expect(classifyLoginError(new TypeError("Failed to fetch")).kind).toBe("network");
    expect(classifyLoginError(new Error("boom")).kind).toBe("other");
  });

  it("speaks English and Persian, and names the next step", () => {
    const nr = classifyLoginError(api("EMAIL_NOT_REGISTERED"));
    expect(loginErrorMessage(nr, "en")).toMatch(/No account is registered/);
    expect(loginErrorMessage(nr, "fa")).toMatch(/ثبت نشده/);
    const wp = classifyLoginError(api("WRONG_PASSWORD", 401, { attempts_left: 1 }));
    expect(loginErrorMessage(wp, "en")).toMatch(/Wrong password.*1 attempt left/);
    expect(loginErrorMessage(wp, "fa")).toMatch(/رمز عبور اشتباه/);
    const rl = classifyLoginError(api("RATE_LIMITED", 429, {}, 840));
    expect(loginErrorMessage(rl, "en")).toMatch(/14 minutes/);
    expect(loginErrorMessage(rl, "fa")).toMatch(/دقیقه/);
  });

  it("validates before sending", () => {
    expect(validateLoginInput("", "", "en")).toEqual({ email: "Enter your email.", password: "Enter your password." });
    expect(validateLoginInput("nope", "x", "en").email).toMatch(/isn't valid/);
    expect(validateLoginInput("nope", "x", "fa").email).toMatch(/ایمیل/);
    expect(validateLoginInput("a@b.co", "x", "en")).toEqual({});
  });
});

describe("google sign-in messages", () => {
  it("has English and Persian text for every backend error code", async () => {
    const { GOOGLE_ERROR_COPY, googleErrorMessage } = await import("../lib/auth-messages");
    const codes = ["cancelled", "state", "token_exchange", "unreachable", "token_invalid", "email_unverified", "account_disabled", "not_configured", "failed"];
    for (const code of codes) {
      expect(Object.keys(GOOGLE_ERROR_COPY.en)).toContain(code);
      expect(googleErrorMessage(code, "en").length).toBeGreaterThan(5);
      expect(googleErrorMessage(code, "fa")).toMatch(/[\u0600-\u06FF]/);
    }
    expect(googleErrorMessage("totally-unknown", "en")).toBe(GOOGLE_ERROR_COPY.en.failed);
    expect(googleErrorMessage(null, "fa")).toBe(GOOGLE_ERROR_COPY.fa.failed);
  });

  it("labels the button in both languages and explains the bare-IP case", async () => {
    const { LOGIN_COPY } = await import("../lib/auth-messages");
    expect(LOGIN_COPY.en.google).toBe("Sign in with Google");
    expect(LOGIN_COPY.fa.google).toBe("ورود با گوگل");
    expect(LOGIN_COPY.en.googleIpHost).toMatch(/structuralai\.ir/);
    expect(LOGIN_COPY.fa.googleIpHost).toMatch(/structuralai\.ir/);
  });
});
