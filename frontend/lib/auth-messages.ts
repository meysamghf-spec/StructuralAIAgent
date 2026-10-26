/** Login error classification + bilingual (EN / FA) copy. Pure, so it is unit-tested. */
import { ApiError } from "./api";
import { isValidEmailAddress } from "./auth-forms";

export type AuthLang = "en" | "fa";
export type LoginErrorKind =
  | "invalid_email"
  | "not_registered"
  | "wrong_password"
  | "rate_limited"
  | "disabled"
  | "network"
  | "other";

export type LoginErrorInfo = {
  kind: LoginErrorKind;
  retryAfterSeconds: number | null;
  attemptsLeft: number | null;
  raw: string;
};

export function classifyLoginError(err: unknown): LoginErrorInfo {
  if (err instanceof ApiError) {
    const kind: LoginErrorKind =
      err.code === "INVALID_EMAIL"
        ? "invalid_email"
        : err.code === "EMAIL_NOT_REGISTERED"
          ? "not_registered"
          : err.code === "WRONG_PASSWORD" || err.code === "INVALID_CREDENTIALS"
            ? "wrong_password"
            : err.code === "RATE_LIMITED" || err.status === 429
              ? "rate_limited"
              : err.code === "ACCOUNT_DISABLED"
                ? "disabled"
                : "other";
    const left = Number(err.details?.attempts_left);
    return { kind, retryAfterSeconds: err.retryAfterSeconds, attemptsLeft: Number.isFinite(left) ? left : null, raw: err.message };
  }
  const message = err instanceof Error ? err.message : "";
  const net = /failed to fetch|network|unable to reach|load failed/i.test(message);
  return { kind: net ? "network" : "other", retryAfterSeconds: null, attemptsLeft: null, raw: message };
}

const digitsFa = (n: number) => n.toLocaleString("fa-IR");

function waitText(seconds: number | null, lang: AuthLang): string {
  const mins = Math.max(1, Math.ceil((seconds ?? 60) / 60));
  return lang === "fa" ? `${digitsFa(mins)} دقیقه` : `${mins} minute${mins === 1 ? "" : "s"}`;
}

export function loginErrorMessage(info: LoginErrorInfo, lang: AuthLang): string {
  const fa = lang === "fa";
  switch (info.kind) {
    case "invalid_email":
      return fa ? "قالب ایمیل درست نیست. نمونه: name@example.com" : "That email address isn't valid. Example: name@example.com";
    case "not_registered":
      return fa ? "حسابی با این ایمیل ثبت نشده است. ایمیل را بررسی کنید یا حساب بسازید." : "No account is registered with this email. Check the address or create an account.";
    case "wrong_password": {
      const left = info.attemptsLeft;
      const extra = left !== null && left <= 2 ? (fa ? ` (${digitsFa(left)} تلاش دیگر باقی مانده است)` : ` (${left} attempt${left === 1 ? "" : "s"} left)`) : "";
      return (fa ? "رمز عبور اشتباه است." : "Wrong password.") + extra;
    }
    case "rate_limited":
      return fa
        ? `به‌دلیل تلاش‌های ناموفق زیاد، ورود موقتاً قفل شد. ${waitText(info.retryAfterSeconds, lang)} دیگر دوباره تلاش کنید.`
        : `Too many failed attempts — sign-in is locked for now. Try again in ${waitText(info.retryAfterSeconds, lang)}.`;
    case "disabled":
      return fa ? "این حساب غیرفعال است. با پشتیبانی تماس بگیرید." : "This account is disabled. Please contact support.";
    case "network":
      return fa ? "اتصال به سرور برقرار نشد. اینترنت را بررسی کنید و دوباره تلاش کنید." : "Unable to reach the server. Check your connection and try again.";
    default:
      return fa ? "ورود انجام نشد. دوباره تلاش کنید." : "Sign-in failed. Please try again.";
  }
}

export type LoginFieldErrors = Partial<Record<"email" | "password", string>>;

/** Client-side checks that run before any request (so a typo never costs a rate-limit attempt). */
export function validateLoginInput(email: string, password: string, lang: AuthLang): LoginFieldErrors {
  const fa = lang === "fa";
  const errors: LoginFieldErrors = {};
  if (!email.trim()) errors.email = fa ? "ایمیل را وارد کنید." : "Enter your email.";
  else if (!isValidEmailAddress(email)) errors.email = loginErrorMessage({ kind: "invalid_email", retryAfterSeconds: null, attemptsLeft: null, raw: "" }, lang);
  if (!password) errors.password = fa ? "رمز عبور را وارد کنید." : "Enter your password.";
  return errors;
}

export const LOGIN_COPY = {
  en: {
    remember: "Remember me",
    rememberHint: "Stay signed in on this device for 30 days.",
    createAccount: "Create account",
    googleSoon: "Sign in with Google isn't available yet.",
    google: "Sign in with Google",
    email: "Email",
    password: "Password",
    submit: "Sign in",
    busy: "Signing in…",
    noAccount: "Don't have an account?",
    signUp: "Sign up",
  },
  fa: {
    remember: "مرا به خاطر بسپار",
    rememberHint: "تا ۳۰ روز در این دستگاه وارد بمانید.",
    createAccount: "ساخت حساب",
    googleSoon: "ورود با گوگل هنوز فعال نشده است.",
    google: "ورود با گوگل",
    email: "ایمیل",
    password: "رمز عبور",
    submit: "ورود",
    busy: "در حال ورود…",
    noAccount: "حساب ندارید؟",
    signUp: "ثبت‌نام",
  },
} as const;
