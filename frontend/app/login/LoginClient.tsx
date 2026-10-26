"use client";

import { useAuth } from "@/hooks/useAuth";
import { AUTH_NAV_LINKS } from "@/lib/auth-forms";
import { completeGoogleSignIn, fetchGoogleSignInEnabled, googleSignInStartUrl } from "@/lib/auth-api";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

export default function LoginClient() {
  const { login, isAuthenticated, loading, refresh } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    void fetchGoogleSignInEnabled().then(setGoogleEnabled);
    if (typeof window === "undefined" || !window.location.hash) return;
    const params = new URLSearchParams(window.location.hash.slice(1));
    const googleToken = params.get("google_token");
    const googleError = params.get("google_error");
    if (!googleToken && !googleError) return;
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    if (googleError) {
      setError(googleError);
      return;
    }
    setBusy(true);
    const next = params.get("next") || "/";
    void completeGoogleSignIn(googleToken as string)
      .then(() => refresh())
      .then(() => router.replace(next.startsWith("/") && !next.startsWith("//") ? next : "/"))
      .catch((err) => setError(err instanceof Error ? err.message : "Google sign-in failed"))
      .finally(() => setBusy(false));
  }, [refresh, router]);

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.replace(nextPath);
    }
  }, [isAuthenticated, loading, nextPath, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      router.replace(nextPath);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack auth-panel">
      <header className="page-header">
        <p className="eyebrow">Sign in</p>
        <h2>Welcome back</h2>
        <p className="subtitle">Sign in to chat with your structural AI.</p>
      </header>

      <form className="card auth-form" onSubmit={handleSubmit}>
        <label className="field-label">
          Email
          <input
            className="input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label className="field-label">
          Password
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error ? <div className="alert error">{error}</div> : null}
        <button className="button" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {googleEnabled ? (
        <a className="button secondary google-signin-button" href={googleSignInStartUrl(nextPath)}>
          <span aria-hidden="true" className="google-signin-g">G</span> Sign in with Google
        </a>
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
