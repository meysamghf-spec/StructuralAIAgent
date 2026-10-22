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
