"use client";

import { useAuth } from "@/hooks/useAuth";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

export default function LoginClient() {
  const { login, isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        <p className="subtitle">Sign in to access your structural engineering workspace.</p>
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

      <p className="muted auth-switch">
        Need an account? <Link href="/register">Create one</Link>
      </p>
    </section>
  );
}
