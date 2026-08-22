# StructuralAIAgent — Production Deployment Guide

## Architecture

- **Backend:** FastAPI (Python 3.12+) on port 8000
- **Frontend:** Next.js on port 3000
- **Database:** PostgreSQL 16+ (`database/migrations/`)

## Environment boundaries

| Environment | Payment gateway | Exchange rates |
|-------------|-----------------|----------------|
| Development | `mock` (default) | `stub` (default) |
| Test/CI | `mock` | `stub` |
| Production | `btcpay` (required) | `coingecko` (recommended) |

Production fails fast if mock payment is used without explicit opt-in, or if BTCPay credentials are missing.

## Required production variables

See `.env.example` for the full list. Minimum production set:

- `APP_ENV=production`
- `AUTH_REQUIRED=true`, `PROJECT_ACCESS_ENFORCED=true`, `ENTITLEMENT_ENFORCEMENT_ENABLED=true`
- `AUTH_JWT_SECRET`, `DATABASE_URL`, `POSTGRES_PASSWORD`
- `CRYPTO_PAYMENT_GATEWAY=btcpay`
- `BTCPAY_SERVER_URL`, `BTCPAY_API_KEY`, `BTCPAY_STORE_ID`
- `CRYPTO_PAYMENT_WEBHOOK_SECRET`, `BTCPAY_WEBHOOK_SECRET`
- `CORS_ORIGINS`, `FILE_STORAGE_ROOT`

## Migrations

```bash
cd backend
python -c "from app.infrastructure.database.migrations import apply_migrations; print(apply_migrations())"
```

Or set `RUN_MIGRATIONS_ON_STARTUP=true`.

## Health checks

- `GET /health` — liveness
- `GET /ready` — database + production payment gateway configured

## Docker

```bash
docker compose -f docker-compose.prod.yml up --build
```

## BTCPay webhook URL

`POST https://<api-host>/api/v1/payments/webhooks/btcpay`

Use header `BTCPay-Sig: sha256=<hmac>`.
