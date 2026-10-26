# SAIA — Production Deployment Guide

## Architecture

- **Backend:** FastAPI (Python 3.12+) on port 8000
- **Frontend:** Next.js on port 3000
- **Database:** PostgreSQL 16+ (`database/migrations/`)
- **File storage:** Local volume at `FILE_STORAGE_ROOT` (uploads, CAD output)
- **Payments:** BTCPay Server (non-custodial crypto invoices)
- **Exchange rates:** CoinGecko public API (no API key required for basic usage)

Place a reverse proxy (nginx, Caddy, Traefik, cloud load balancer) in front for TLS termination and path routing. The included `docker-compose.prod.yml` does **not** provide HTTPS or a public domain.

## Environment boundaries

| Environment | Payment gateway | Exchange rates |
|-------------|-----------------|----------------|
| Development | `mock` (default) | `stub` (default) |
| Test/CI | `mock` | `stub` |
| Production | `btcpay` (required) | `coingecko` (recommended) |

Production fails fast at startup if mock payment is used without explicit opt-in, BTCPay credentials are missing, auth/entitlement enforcement is disabled, or `FILE_STORAGE_ROOT` is unset.

## Required production variables

See `.env.example` for the full list. Minimum production set:

| Variable | Purpose |
|----------|---------|
| `APP_ENV=production` | Enables production validation |
| `AUTH_REQUIRED=true` | JWT required on protected routes |
| `PROJECT_ACCESS_ENFORCED=true` | Project ownership checks |
| `ENTITLEMENT_ENFORCEMENT_ENABLED=true` | Paid-feature gating |
| `AUTH_ALLOW_LEGACY_ACTOR=false` | Disables `X-Actor-Id` bypass |
| `AUTH_JWT_SECRET` | Long random signing secret (you generate) |
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_PASSWORD` | DB password (preferred over embedding in URL) |
| `FILE_STORAGE_ROOT` | Persistent writable directory for uploads/CAD |
| `CRYPTO_PAYMENT_GATEWAY=btcpay` | Real payment provider |
| `BTCPAY_SERVER_URL` | Your BTCPay instance base URL |
| `BTCPAY_API_KEY` | BTCPay Greenfield API key |
| `BTCPAY_STORE_ID` | BTCPay store identifier |
| `CRYPTO_PAYMENT_WEBHOOK_SECRET` | HMAC secret for payment webhooks |
| `BTCPAY_WEBHOOK_SECRET` | BTCPay webhook signing secret |
| `CORS_ORIGINS` | Comma-separated frontend origin(s), e.g. `https://app.example.com` |
| `NEXT_PUBLIC_API_URL` | Frontend build-time API base, e.g. `https://api.example.com` |
| `TRUST_PROXY_HEADERS=true` | Required when behind reverse proxy |

Optional ops:

- `RUN_MIGRATIONS_ON_STARTUP=true` — apply SQL migrations on backend boot
- `LOG_LEVEL=INFO`
- `EXCHANGE_RATE_PROVIDER=coingecko`

## External resources you must provide

Do **not** commit real values. Create a host-level `.env` (or secret manager entries) before `docker compose up`.

1. **Domain + DNS** — e.g. `app.example.com` (frontend), `api.example.com` (backend)
2. **TLS certificate** — via Let's Encrypt, cloud LB, or your reverse proxy
3. **Reverse proxy config** — route `/` → frontend:3000, `/api` and `/health` `/ready` → backend:8000
4. **PostgreSQL** — included in compose, or managed Postgres with connection string
5. **BTCPay Server** — self-hosted or hosted instance with store + API key + webhook
6. **Secrets** — `AUTH_JWT_SECRET`, `POSTGRES_PASSWORD`, webhook secrets (generate locally)
7. **Persistent volume** — for PostgreSQL data and `FILE_STORAGE_ROOT` (compose defines named volumes)

### BTCPay webhook URL

Register in your BTCPay store:

```
POST https://<api-host>/api/v1/payments/webhooks/btcpay
```

Use header `BTCPay-Sig: sha256=<hmac>` matching `BTCPAY_WEBHOOK_SECRET` / `CRYPTO_PAYMENT_WEBHOOK_SECRET`.

### CoinGecko

No account or API key is required for the default public price endpoint. Rate limits apply; monitor if you expect high payment volume.

### First user / bootstrap

With `AUTH_REQUIRED=true`, register the first account via:

```
POST /api/v1/auth/register
```

There is no built-in admin seed user. Restrict network access or register immediately after deploy.

## Migrations

Migrations are idempotent (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`) and safe to re-run on startup.

Manual apply:

```bash
cd backend
python -c "from app.infrastructure.database.migrations import apply_migrations; print(apply_migrations())"
```

Or set `RUN_MIGRATIONS_ON_STARTUP=true` (default in `docker-compose.prod.yml`).

## Health checks

| Endpoint | Use | Success |
|----------|-----|---------|
| `GET /health` | Liveness | Always `200` when process is up |
| `GET /ready` | Readiness | `200` when DB + file storage OK; production also requires `btcpay` gateway configured. Returns `503` when not ready. |

Docker Compose configures a backend healthcheck on `/ready`.

## Docker

Create `.env` in the repo root with production secrets, then:

```bash
docker compose -f docker-compose.prod.yml up --build
```

Build args:

- `NEXT_PUBLIC_API_URL` — must match the public API URL users' browsers will call

Volumes:

- `pgdata` — PostgreSQL data
- `file_storage` — uploaded files and generated CAD artifacts

## Estimated deployment cost categories

| Category | Typical options |
|----------|-----------------|
| Compute | VPS ($5–40/mo), cloud VM, or PaaS container service |
| Database | Included in compose, or managed Postgres ($15–100+/mo) |
| Storage | Block volume for DB + files ($1–20/mo depending on size) |
| Domain | Registrar ($10–15/yr) |
| TLS | Free (Let's Encrypt) or included with cloud LB |
| BTCPay | Self-hosted on same/different VPS, or BTCPay third-party host |
| CoinGecko | Free tier (public API); paid plans if rate limits become an issue |
| Egress/bandwidth | Usually included in VPS; monitor for large file uploads |

## Production readiness checklist

- [ ] `.env` with all required variables (no mock payment in production)
- [ ] `CORS_ORIGINS` matches frontend URL
- [ ] `NEXT_PUBLIC_API_URL` set at frontend **build** time
- [ ] Reverse proxy with HTTPS configured
- [ ] BTCPay webhook registered and secrets aligned
- [ ] Persistent volumes for DB and file storage
- [ ] First user registered (or registration endpoint restricted)
- [ ] `/ready` returns `200` before sending traffic

## Sign in with Google (optional)
Disabled unless all three are set in `.env.production` (backend):
```
GOOGLE_CLIENT_ID=<OAuth client id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<OAuth client secret>
GOOGLE_REDIRECT_URI=https://<your-domain>/api/v1/auth/google/callback
# optional: GOOGLE_POST_LOGIN_URL=https://<your-domain>/login
```
Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web application):
- Authorized JavaScript origins: `https://<your-domain>`
- Authorized redirect URIs: `https://<your-domain>/api/v1/auth/google/callback`
- OAuth consent screen scopes: `openid`, `email`, `profile`.
Google accounts are linked to existing users by verified email; unknown emails get a new user.
