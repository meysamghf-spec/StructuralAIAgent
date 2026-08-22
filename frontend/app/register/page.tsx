"use client";

import { useAuth } from "@/hooks/useAuth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

export default function RegisterPage() {
  const { register, isAuthenticated, loading } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, loading, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(email.trim(), password, displayName.trim() || undefined);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack auth-panel">
      <header className="page-header">
        <p className="eyebrow">Create account</p>
        <h2>Register</h2>
        <p className="subtitle">Create an account to manage projects and engineering workflows.</p>
      </header>

      <form className="card auth-form" onSubmit={handleSubmit}>
        <label className="field-label">
          Display name
          <input
            className="input"
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Optional"
          />
        </label>
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
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>
        {error ? <div className="alert error">{error}</div> : null}
        <button className="button" type="submit" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="muted auth-switch">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </section>
  );
}
