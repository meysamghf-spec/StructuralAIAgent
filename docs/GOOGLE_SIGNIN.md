# Sign in with Google

OAuth 2.0 authorization-code flow, scopes `openid email profile` only.

1. Google Cloud Console -> APIs & Services -> Credentials -> OAuth client ID (Web application).
2. Authorized redirect URI (exactly): `https://structuralai.ir/api/auth/google/callback`
   (Google does not allow a bare IP such as `http://194.5.207.71`; IP access simply has no Google sign-in.)
3. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the server env (`.env.production`) and recreate the backend.
   `GOOGLE_REDIRECT_URI` is optional and defaults to the URI above. Never commit or log these values.

Behaviour
- The "Sign in with Google" button shows only when both variables are set; otherwise the login page shows a short note.
- `/api/auth/google/start` sets a short-lived httpOnly nonce cookie and signs `state`; the callback rejects a missing/forged/expired state.
- The ID token is checked (via Google's tokeninfo): audience = client id, issuer, expiry, nonce and `email_verified`.
- Accounts are linked by verified email (case-insensitive): an existing user signs in, otherwise one is created.
- Failures return to `/login#google_error=...` with a readable message.

Auth/session env: `AUTH_REMEMBER_EXPIRY_HOURS` (default 720), `AUTH_MAX_LOGIN_FAILURES` (5), `AUTH_LOCKOUT_SECONDS` (900).
