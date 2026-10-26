"use client";

import { useAuth } from "@/hooks/useAuth";
import {
  AUTH_NAV_LINKS,
  AUTH_ROUTES,
  REGISTER_PAGE,
  formatRegistrationError,
  validateRegistrationForm,
  type RegistrationFieldErrors,
} from "@/lib/auth-forms";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

export default function RegisterClient() {
  const { register, isAuthenticated, loading } = useAuth();
  const router = useRouter();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<RegistrationFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.replace(AUTH_ROUTES.dashboard);
    }
  }, [isAuthenticated, loading, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    const validation = validateRegistrationForm({
      email,
      password,
      confirmPassword,
      displayName,
    });

    if (!validation.ok) {
      setFieldErrors(validation.fieldErrors);
      return;
    }

    setFieldErrors({});
    setBusy(true);
    try {
      await register(validation.email, validation.password, validation.displayName);
      router.replace(AUTH_ROUTES.dashboard);
    } catch (err) {
      setFormError(formatRegistrationError(err));
    } finally {
      setBusy(false);
    }
  }

  function clearFieldError(field: keyof RegistrationFieldErrors) {
    setFieldErrors((current) => {
      if (!current[field]) {
        return current;
      }
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  return (
    <section className="panel-stack auth-panel">
      <header className="page-header">
        <p className="eyebrow">{REGISTER_PAGE.eyebrow}</p>
        <h2>{REGISTER_PAGE.heading}</h2>
        <p className="subtitle">
          Create an account to chat with your structural AI — analysis, design, validation, approval and memory.
        </p>
      </header>

      <form className="card auth-form" onSubmit={handleSubmit} noValidate>
        <label className="field-label">
          Display name <span className="field-optional">(optional)</span>
          <input
            className="input"
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(event) => {
              setDisplayName(event.target.value);
              clearFieldError("displayName");
            }}
            placeholder="How you'd like to be shown in the workspace"
          />
          {fieldErrors.displayName ? (
            <span className="field-error">{fieldErrors.displayName}</span>
          ) : null}
        </label>

        <label className="field-label">
          Email
          <input
            className="input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              clearFieldError("email");
            }}
            required
          />
          {fieldErrors.email ? <span className="field-error">{fieldErrors.email}</span> : null}
        </label>

        <label className="field-label">
          Password
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              clearFieldError("password");
            }}
            required
          />
          {fieldErrors.password ? (
            <span className="field-error">{fieldErrors.password}</span>
          ) : null}
        </label>

        <label className="field-label">
          Confirm password
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => {
              setConfirmPassword(event.target.value);
              clearFieldError("confirmPassword");
            }}
            required
          />
          {fieldErrors.confirmPassword ? (
            <span className="field-error">{fieldErrors.confirmPassword}</span>
          ) : null}
        </label>

        {formError ? <div className="alert error">{formError}</div> : null}

        <button className="button" type="submit" disabled={busy}>
          {busy ? REGISTER_PAGE.submitBusy : REGISTER_PAGE.submitIdle}
        </button>
      </form>

      <p className="muted auth-switch">
        {AUTH_NAV_LINKS.signUpToSignIn.prompt}{" "}
        <Link href={AUTH_NAV_LINKS.signUpToSignIn.href} className="auth-inline-link">
          {AUTH_NAV_LINKS.signUpToSignIn.label}
        </Link>
      </p>
    </section>
  );
}
