# Crypto billing: go-live checklist

Payments are crypto only. Until the env vars below are set, every invoice is a test invoice ("Simulate payment").
Set them in `.env.production`, then rebuild the backend. Each asset goes live on its own.

| Env var | Enables | Notes |
|---|---|---|
| `CRYPTO_TRON_ADDRESS` | USDT-TRC20, TRX | A Tron address you control (watch-only, no key on the server). |
| `TRONGRID_API_KEY` | (recommended) | Free TronGrid key; it raises the rate limit. |
| `CRYPTO_EVM_ADDRESS` | USDT/USDC on BEP20, ERC20 and Polygon; ETH, BNB | One 0x address works on all EVM chains. Override per chain with `CRYPTO_BSC_ADDRESS`, `CRYPTO_ETH_ADDRESS` or `CRYPTO_POLYGON_ADDRESS`. |
| `CRYPTO_ETH_RPC`, `CRYPTO_BSC_RPC`, `CRYPTO_POLYGON_RPC` | (optional) | Public RPCs are the default; use a private RPC for reliability. |
| `CRYPTO_TON_ADDRESS` | TON | Uses toncenter. |
| `BTCPAY_SERVER_URL`, `BTCPAY_API_KEY`, `BTCPAY_STORE_ID` | BTC on-chain, BTC Lightning, LTC | Self-hosted BTCPay Server on a non-Iran VPS. The API key needs invoice view and create permissions. |
| `CRYPTO_RATES_JSON` | (optional) | Fixed USD prices, for example `{"BTC":65000}`. Without it, CoinGecko prices are used and locked for the invoice's life. |
| `CRYPTO_INVOICE_MINUTES` | (optional) | Invoice expiry time. The default is 30. |

Matching: each invoice gets a unique amount (the last 3 decimals), and the watcher matches transfers of exactly that amount to your address.

## USDT on BNB Smart Chain (BEP20): the verified path

This is the first asset with real automatic detection. The server is watch-only: it holds no private key.

| Env var | Default | Notes |
|---|---|---|
| `CRYPTO_BSC_ADDRESS` | none | Your receiving address (EIP-55 checksum is validated; a bad address is refused and logged). Falls back to `CRYPTO_EVM_ADDRESS`. |
| `CRYPTO_LIVE_ASSETS` | all configured | Set `usdt-bep20` so only this verified asset is live. |
| `CRYPTO_BSC_RPC_URLS` | built-in public list | Comma-separated, tried in order with failover. Put a private RPC first for reliability. The legacy `CRYPTO_BSC_RPC` is still honoured. |
| `CRYPTO_CONFIRMATIONS` | 30 | BSC blocks are about 0.45 s, so 30 is about 14 s. |
| `CRYPTO_OVERPAY_TOLERANCE_USDT` | 1 | A payment up to this much above the tagged amount is accepted; more goes to admin review. |
| `CRYPTO_WATCHER` / `CRYPTO_WATCH_SECONDS` | on / 20 | Background scanner. Pay-page polling also triggers a throttled scan. |
| `CRYPTO_INVOICE_MINUTES` | 30 | Payment window. A transfer arriving within 24 h after it is still matched (marked late). |
| `BILLING_ADMIN_ACCOUNTS` | none | Comma-separated account ids or emails that may use `/billing/admin/*`. Without it the admin routes return 403. |
| `APP_ENV=production` | | In production, simulated payments are refused. An asset that is not live is unavailable, so nobody can get a free plan. |

Token: USDT (BSC-USD), contract `0x55d398326f99059fF775485246999027B3197955`, 18 decimals.
Matching: the invoice amount carries a unique tag of 0.001 to 0.999 USDT. A transfer to your address with that exact amount and enough confirmations activates the plan, once only.
Edge cases: underpaid never auto-activates (shown to the user, reviewed by admin); overpay within tolerance activates; larger overpay, ambiguous amount, or duplicate go to review; expired invoices can still be rescued by the user pasting the tx hash or by an admin.

Admin endpoints (need `BILLING_ADMIN_ACCOUNTS`):
- `GET /api/v1/billing/admin/payments`: pending invoices plus transfers needing review.
- `POST /api/v1/billing/admin/invoices/{id}/confirm` with `{"tx": "0x…", "note": "why"}`: manual confirm; a tx is verified on-chain and the note is mandatory.

Read-only live check (no payments): `python scripts/check_bep20_live.py <your address>`.

First real test (by the owner only): create a Pro 1-month invoice on the pay page, send the exact tagged amount of USDT (BEP20) from your own wallet, and watch the status move to "detected N of 30", then "paid".
Note: `.env.production.example` ships with `PAYMENTS_ENABLED=false`; switch it to `true` only when you go live.
