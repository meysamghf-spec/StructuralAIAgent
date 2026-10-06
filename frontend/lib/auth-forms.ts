/** Shared auth form validation and navigation copy for Sign In / Sign Up. */

export const AUTH_ROUTES = {
  signIn: "/login",
  signUp: "/register",
  dashboard: "/",
} as const;

export const AUTH_NAV_LINKS = {
  signInToSignUp: {
    prompt: "Don't have an account?",
    label: "Sign up",
    href: AUTH_ROUTES.signUp,
  },
  signUpToSignIn: {
    prompt: "Already have an account?",
    label: "Sign in",
    href: AUTH_ROUTES.signIn,
  },
} as const;

export type RegistrationFormInput = {
  email: string;
  password: string;
  confirmPassword: string;
  displayName: string;
};

export type RegistrationFieldErrors = Partial<
  Record<"email" | "password" | "confirmPassword" | "displayName", string>
>;

export type RegistrationValidationResult =
  | {
      ok: true;
      email: string;
      password: string;
      displayName?: string;
    }
  | {
      ok: false;
      fieldErrors: RegistrationFieldErrors;
    };

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmailAddress(email: string): boolean {
  return EMAIL_PATTERN.test(email.trim());
}

export function validateRegistrationForm(
  input: RegistrationFormInput,
): RegistrationValidationResult {
  const fieldErrors: RegistrationFieldErrors = {};
  const email = input.email.trim();

  if (!email) {
    fieldErrors.email = "Email is required.";
  } else if (!isValidEmailAddress(email)) {
    fieldErrors.email = "Enter a valid email address.";
  }

  if (!input.password) {
    fieldErrors.password = "Password is required.";
  }

  if (!input.confirmPassword) {
    fieldErrors.confirmPassword = "Please confirm your password.";
  } else if (input.password !== input.confirmPassword) {
    fieldErrors.confirmPassword = "Passwords do not match.";
  }

  if (Object.keys(fieldErrors).length > 0) {
    return { ok: false, fieldErrors };
  }

  const displayName = input.displayName.trim();
  return {
    ok: true,
    email,
    password: input.password,
    displayName: displayName || undefined,
  };
}

function looksLikeInternalError(message: string): boolean {
  return (
    /traceback/i.test(message) ||
    /\n\s+at /i.test(message) ||
    /^\s*at .+:\d+:\d+/m.test(message) ||
    message.includes("Unexpected token") ||
    message.includes("SyntaxError")
  );
}

export function formatRegistrationError(error: unknown): string {
  if (!(error instanceof Error)) {
    return "An unexpected error occurred. Please try again.";
  }

  const message = error.message.trim();
  if (!message || looksLikeInternalError(message)) {
    return "Registration failed. Please try again.";
  }

  const lower = message.toLowerCase();
  if (
    lower.includes("failed to fetch") ||
    lower.includes("network") ||
    lower.includes("unable to reach")
  ) {
    return "Unable to reach the server. Check your connection and try again.";
  }

  if (lower.includes("request failed")) {
    return "Registration failed. Please try again.";
  }

  return message;
}

/** Stable copy and field keys used by the register page (for tests and UI consistency). */
export const REGISTER_PAGE = {
  eyebrow: "Sign up",
  heading: "Create your account",
  fields: ["displayName", "email", "password", "confirmPassword"] as const,
  submitIdle: "Create account",
  submitBusy: "Creating account…",
} as const;
