# Sign in with Google

Server-side OAuth 2.0 **authorization code + PKCE (S256)** with OpenID Connect, scopes `openid email profile` only.
Everything that talks to Google runs on the backend, so browsers (including in Iran) only ever talk to
`structuralai.ir`; they never need to reach Google's token endpoint. (The user's browser still has to open
`accounts.google.com` once for the consent/account-picker screen.)

## Env (backend, `.env.production`)

| Variable | Value |
| --- | --- |
| `GOOGLE_OAUTH_ENABLED` | `true` (default `false` → no button, endpoints answer "not configured") |
| `GOOGLE_CLIENT_ID` | `686563514296-c92jjk1hvk1scjkskp8368s130iv6rfn.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | set **on the server only**; never commit/log/paste it |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://structuralai.ir/api/auth/google/callback` (older name `GOOGLE_REDIRECT_URI` still works; the new one wins) |
| `GOOGLE_POST_LOGIN_URL` | optional, absolute login-page URL; default = `<request origin>/login` |
| `GOOGLE_OAUTH_PROXY` | optional outbound proxy for the backend→Google calls only (`http://host:port`, `socks5://…`). Unset = direct. |
| `GOOGLE_OAUTH_TIMEOUT_SECONDS` | optional, default `15` |

> **Important:** earlier builds enabled Google whenever the id and secret were present. The new flag defaults to
> **off**, so after deploying you must add `GOOGLE_OAUTH_ENABLED=true` or the button disappears.

## Google Cloud Console (APIs & Services → Credentials → the OAuth client "Web application")

- **Authorized JavaScript origins**
  - `https://structuralai.ir`
  - `https://www.structuralai.ir`
- **Authorized redirect URIs** (exact match, no trailing slash)
  - `https://structuralai.ir/api/auth/google/callback`
  - `https://www.structuralai.ir/api/auth/google/callback` (only if users reach the site on `www`; the backend's `GOOGLE_OAUTH_REDIRECT_URI` decides which one is *sent*, so set it to the canonical host)
- Google rejects bare IPs (`http://194.5.207.71`) as redirect URIs → on the IP address the login page shows a hint "use https://structuralai.ir" instead of the button.
- **OAuth consent screen**: scopes `openid`, `email`, `profile` are non-sensitive (no Google verification needed).
  If the publishing status is **Testing**, only the listed *Test users* can sign in (everyone else sees Google's
  "access blocked" page, 100 test users max, and refresh grants expire after 7 days – irrelevant here since we only sign in).
  Add Meysam's Gmail addresses as test users, or click **Publish app → In production** to open it to everyone.

## Flow

1. Login page asks `GET /api/v1/auth/google/config` → `{enabled, reason}`; the button renders only when `enabled`.
2. Button → `GET /api/v1/auth/google/start?next=/…&remember=true|false`. The backend creates a nonce, sets the
   httpOnly cookie `sa_google_nonce` (path `/api`, 10 min), derives the PKCE verifier as
   `HMAC(jwt_secret, "pkce:"+nonce)` (nothing extra stored) and redirects to Google with an HMAC-signed `state`
   (carries nonce, `next`, remember flag, expiry).
3. Google → `GET /api/auth/google/callback?code&state` (the `/api/v1/auth/google/callback` route is the same handler).
   The backend checks: state signature + expiry + match with the nonce cookie, exchanges the code (with the PKCE
   verifier) at Google's token endpoint over TLS, then validates the id_token claims: `iss`, `aud`/`azp` = client id,
   `exp`, `nonce`, `sub`, `email`, **`email_verified == true`**. The id_token comes straight from Google over TLS, so its
   signature is not re-verified (OIDC Core §3.1.3.7).
4. Account: existing user with the same verified email (case-insensitive) is signed in (linked); otherwise a user +
   account is created. Disabled accounts are refused.
5. The backend sets the **same `saia_session` httpOnly cookie** as email login (path `/api/v1/auth`; lifetime follows
   *Remember me* = `AUTH_REMEMBER_EXPIRY_HOURS`, default 720 h) and redirects to `/login#google=ok&r=…&next=…` (the fragment carries no secret); the page
   calls `POST /api/v1/auth/session` (same as page-reload restore) to get the bearer token, then goes to `next`.
   No token is ever placed in a URL.
6. Failures redirect to `/login#google_error=<code>` with a stable code (`cancelled`, `state`, `token_exchange`,
   `unreachable`, `token_invalid`, `email_unverified`, `account_disabled`, `not_configured`, `failed`), translated fa/en
   on the page. Raw exception text is never shown.

## nginx: callback blocked by the staging gate (proposed – NOT applied)

Production nginx protects the site with a basic-auth/cookie gate (cookie `sa_gate`); `/api/` answers **401** to any
browser that does not already carry that cookie. The Google callback is a top-level navigation back from
`accounts.google.com`; it works only if the same browser already passed the gate on that exact host. It breaks for a
different browser/profile, an in-app browser, or a visit via `www.` vs the apex host. Proposed exception, in both the
`:80` and `:443` server blocks, placed **before** the generic `location /api/`:

```nginx
# Google OIDC callback: no gate cookie is available when Google redirects back.
# Safe: the handler needs a valid HMAC state + the httpOnly nonce cookie set by /start, and does nothing else.
location = /api/auth/google/callback {
    proxy_pass http://127.0.0.1:8000;   # same upstream as the existing /api/ block
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Copy the real `proxy_pass`/`proxy_set_header` lines from the existing `/api/` location instead of the ones above.
`/api/v1/auth/google/start` stays behind the gate (the user is on the gated site when clicking). Once the gate is
removed this block is unnecessary. Check with `nginx -t` then reload.

## Rollout

1. Merge the PR (not done automatically) and back up `.env.production` and the compose files.
2. Google Cloud Console: add the origins/redirect URIs above; add test users or publish.
3. Add `GOOGLE_OAUTH_ENABLED=true` (+ id/secret/redirect already on the server) to `.env.production`.
4. Deploy backend + frontend; apply the nginx exception, `nginx -t && nginx -s reload`.
5. Smoke test on `https://structuralai.ir/login` with a test user: button visible → account picker → back signed in;
   a second sign-in must reuse the same account; "Remember me" off → session cookie without Max-Age.
6. Watch backend logs for the `saia.google_signin` logger (failure code only; no tokens or secrets are logged).

## Rollback

- Instant: `GOOGLE_OAUTH_ENABLED=false` + recreate backend → button hidden, endpoints refuse. Email login is untouched.
- Full: redeploy the previous image; remove the nginx location. Users created through Google keep working with
  *password reset*; no schema change is part of this feature.

## If the server cannot reach Google

Set `GOOGLE_OAUTH_PROXY` (e.g. `http://10.0.0.5:3128`) – used only for the token request. The Arvan host and backend
container were checked reachable directly (no proxy needed) on 2026-10-27.

Auth/session env: `AUTH_REMEMBER_EXPIRY_HOURS` (default 720), `AUTH_MAX_LOGIN_FAILURES` (5), `AUTH_LOCKOUT_SECONDS` (900).
