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
