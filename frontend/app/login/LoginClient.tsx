"use client";

import { useAuth } from "@/hooks/useAuth";
import { useUiLang } from "@/hooks/useUiLang";
import { AUTH_NAV_LINKS } from "@/lib/auth-forms";
import { completeGoogleSignIn, fetchGoogleSignInEnabled, googleSignInStartUrl } from "@/lib/auth-api";
import {
  LOGIN_COPY,
  classifyLoginError,
  loginErrorMessage,
  validateLoginInput,
  type LoginErrorInfo,
  type LoginFieldErrors,
} from "@/lib/auth-messages";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

export default function LoginClient() {
  const { login, isAuthenticated, loading, refresh } = useAuth();
  const { lang, t } = useUiLang();
  const copy = LOGIN_COPY[lang];
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<LoginFieldErrors>({});
  const [errorInfo, setErrorInfo] = useState<LoginErrorInfo | null>(null);
  const [plainError, setPlainError] = useState<string | null>(null);
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    void fetchGoogleSignInEnabled().then(setGoogleEnabled);
    if (typeof window === "undefined" || !window.location.hash) return;
    const params = new URLSearchParams(window.location.hash.slice(1));
    const googleToken = params.get("google_token");
    const googleError = params.get("google_error");
    if (!googleToken && !googleError) return;
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    if (googleError) {
      setPlainError(googleError);
      return;
    }
    setBusy(true);
    const next = params.get("next") || "/";
    void completeGoogleSignIn(googleToken as string)
      .then(() => refresh())
      .then(() => router.replace(next.startsWith("/") && !next.startsWith("//") ? next : "/"))
      .catch((err) => setPlainError(err instanceof Error ? err.message : "Google sign-in failed"))
      .finally(() => setBusy(false));
  }, [refresh, router]);

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.replace(nextPath);
    }
  }, [isAuthenticated, loading, nextPath, router]);

  // Tick while the account is locked so the form re-enables itself.
  useEffect(() => {
    if (!lockedUntil) return;
    const id = window.setInterval(() => {
      setNow(Date.now());
      if (Date.now() >= lockedUntil) setLockedUntil(null);
    }, 1000);
    return () => window.clearInterval(id);
  }, [lockedUntil]);

  const locked = lockedUntil !== null && now < lockedUntil;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setErrorInfo(null);
    setPlainError(null);
    const invalid = validateLoginInput(email, password, lang);
    setFieldErrors(invalid);
    if (invalid.email || invalid.password) return;
    setBusy(true);
    try {
      await login(email.trim(), password, remember);
      router.replace(nextPath);
    } catch (err) {
      const info = classifyLoginError(err);
      if (info.kind === "invalid_email") {
        setFieldErrors({ email: loginErrorMessage(info, lang) });
      } else {
        setErrorInfo(info);
      }
      if (info.kind === "rate_limited") {
        setNow(Date.now());
        setLockedUntil(Date.now() + (info.retryAfterSeconds ?? 60) * 1000);
      }
    } finally {
      setBusy(false);
    }
  }

  const registerHref = `${AUTH_NAV_LINKS.signInToSignUp.href}?email=${encodeURIComponent(email.trim())}`;

  return (
    <section className="panel-stack auth-panel">
      <header className="page-header">
        <p className="eyebrow">{t("Sign in")}</p>
        <h2>{t("Welcome back")}</h2>
        <p className="subtitle">{t("Sign in to chat with your structural AI.")}</p>
      </header>

      <form className="card auth-form" onSubmit={handleSubmit} noValidate>
        <label className="field-label" htmlFor="login-email">
          {copy.email}
          <input
            id="login-email"
            name="email"
            className="input"
            type="email"
            inputMode="email"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            dir="ltr"
            value={email}
            aria-invalid={Boolean(fieldErrors.email) || errorInfo?.kind === "not_registered"}
            aria-describedby={fieldErrors.email ? "login-email-error" : undefined}
            onChange={(event) => {
              setEmail(event.target.value);
              if (fieldErrors.email) setFieldErrors((c) => ({ ...c, email: undefined }));
              if (errorInfo?.kind === "not_registered") setErrorInfo(null);
            }}
            required
          />
          {fieldErrors.email ? (
            <span id="login-email-error" className="field-error" role="alert">
              {fieldErrors.email}
            </span>
          ) : null}
        </label>
        <label className="field-label" htmlFor="login-password">
          {copy.password}
          <input
            id="login-password"
            name="password"
            className="input"
            type="password"
            autoComplete="current-password"
            dir="ltr"
            value={password}
            aria-invalid={Boolean(fieldErrors.password) || errorInfo?.kind === "wrong_password"}
            aria-describedby={fieldErrors.password ? "login-password-error" : undefined}
            onChange={(event) => {
              setPassword(event.target.value);
              if (fieldErrors.password) setFieldErrors((c) => ({ ...c, password: undefined }));
              if (errorInfo?.kind === "wrong_password") setErrorInfo(null);
            }}
            required
          />
          {fieldErrors.password ? (
            <span id="login-password-error" className="field-error" role="alert">
              {fieldErrors.password}
            </span>
          ) : null}
        </label>

        <label className="remember-row" htmlFor="login-remember">
          <input
            id="login-remember"
            name="remember"
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          <span>
            {copy.remember}
            <small className="muted"> — {copy.rememberHint}</small>
          </span>
        </label>

        {errorInfo ? (
          <div className="alert error login-alert" role="alert" data-kind={errorInfo.kind}>
            <p>{loginErrorMessage(errorInfo, lang)}</p>
            {errorInfo.kind === "not_registered" ? (
              <Link className="button secondary login-alert-action" href={registerHref}>
                {copy.createAccount}
              </Link>
            ) : null}
          </div>
        ) : null}
        {plainError ? (
          <div className="alert error" role="alert">
            {plainError}
          </div>
        ) : null}

        <button className="button" type="submit" disabled={busy || locked}>
          {busy ? copy.busy : copy.submit}
        </button>
      </form>

      {googleEnabled === true ? (
        <a className="button secondary google-signin-button" href={googleSignInStartUrl(nextPath)}>
          <span aria-hidden="true" className="google-signin-g">G</span> {copy.google}
        </a>
      ) : googleEnabled === false ? (
        <p className="muted auth-switch google-note">{copy.googleSoon}</p>
      ) : null}

      <p className="muted auth-switch">
        {AUTH_NAV_LINKS.signInToSignUp.prompt}{" "}
        <Link href={AUTH_NAV_LINKS.signInToSignUp.href} className="auth-inline-link">
          {AUTH_NAV_LINKS.signInToSignUp.label}
        </Link>
      </p>
    </section>
  );
}
