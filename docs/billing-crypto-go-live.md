# Crypto billing: go-live checklist

Payments are crypto only. Until the env vars below are set, every invoice is a test invoice ("Simulate payment").
Set them in `.env.production`, then rebuild the backend. Each asset goes live on its own.

| Env var | Enables | Notes |
|---|---|---|
| `CRYPTO_TRON_ADDRESS` | USDT on Tron (TRC20), live. TRX native is never live | A Tron address you control (watch-only, no key on the server). Base58check-validated. |
| `TRONGRID_API_KEY` | (optional) | Free TronGrid key; raises the rate limit. Sent only to `api.trongrid.io`, never logged. |
| `CRYPTO_BTC_ADDRESS` | Bitcoin on-chain, live (replaces the BTCPay path for `btc-onchain`) | A Bitcoin address you control (watch-only). Bech32/bech32m/legacy, mainnet only; the checksum is validated. |
| `CRYPTO_EVM_ADDRESS` | USDT/USDC on BEP20, ERC20 and Polygon (live). ETH and BNB native are never live (see below) | One 0x address works on all EVM chains. Override per chain with `CRYPTO_BSC_ADDRESS`, `CRYPTO_ETH_ADDRESS` or `CRYPTO_POLYGON_ADDRESS`. |
| `CRYPTO_ETH_RPC_URLS`, `CRYPTO_BSC_RPC_URLS`, `CRYPTO_POLYGON_RPC_URLS` | (optional) | Comma-separated, tried first, then the built-in public list. Use a private RPC for reliability (legacy `CRYPTO_<CHAIN>_RPC` still works). |
| `CRYPTO_TON_ADDRESS` | TON | Uses toncenter. |
| `BTCPAY_SERVER_URL`, `BTCPAY_API_KEY`, `BTCPAY_STORE_ID` | BTC Lightning, LTC (not enabled: see below) | Self-hosted BTCPay Server on a non-Iran VPS. The API key needs invoice view and create permissions. |
| `CRYPTO_RATES_JSON` | (optional) | Fixed USD prices, for example `{"BTC":65000}`. Without it, CoinGecko prices are used and locked for the invoice's life. |
| `CRYPTO_INVOICE_MINUTES` | (optional) | Invoice expiry time. The default is 30. |

Matching: each invoice gets a unique amount (the last 3 decimals), and the watcher matches transfers of exactly that amount to your address.

## The eight live options (USDT/USDC on three EVM chains, USDT on Tron, Bitcoin on-chain)

All of them are detected automatically from a receiving address. The server is watch-only: it holds no private key.
Live assets: `usdt-bep20, usdc-bep20, usdt-polygon, usdc-polygon, usdt-erc20, usdc-erc20, usdt-trc20, btc-onchain`.

## USDT and USDC on BNB Smart Chain, Polygon and Ethereum: the verified path

These six assets have real automatic detection from ONE receiving address.

### Exact values to set in `.env.production`

```
CRYPTO_EVM_ADDRESS=0x17F5FC2fC7ca5066bBF96d0E1687122553410022
CRYPTO_TRON_ADDRESS=TDuvB4k5foeTrUFFeDdnpCHVbn6M6QgSwf
CRYPTO_BTC_ADDRESS=bc1qd3fyhu2a97hhgezd7sf7rk6h740w53xa6wwpd3
CRYPTO_LIVE_ASSETS=usdt-bep20,usdc-bep20,usdt-polygon,usdc-polygon,usdt-erc20,usdc-erc20,usdt-trc20,btc-onchain
BILLING_ADMIN_ACCOUNTS=<your account email or id>
PAYMENTS_ENABLED=true
ENTITLEMENT_ENFORCEMENT_ENABLED=true
```

Notes on these:
- `CRYPTO_EVM_ADDRESS` is used for all three chains. `CRYPTO_BSC_ADDRESS` / `CRYPTO_POLYGON_ADDRESS` / `CRYPTO_ETH_ADDRESS` override it per chain (the older single-chain setup `CRYPTO_BSC_ADDRESS=...` keeps working). The EIP-55 checksum is validated; a bad address is refused and logged, and the assets stay hidden.
- `CRYPTO_LIVE_ASSETS` is an allowlist. Nothing outside it can be paid, even if its address or server is configured. Remove an id from the list to switch that asset off.
- `PAYMENTS_ENABLED=true` requires `ENTITLEMENT_ENFORCEMENT_ENABLED=true` in production (startup validation fails otherwise). **Turning enforcement on activates paid-feature gating across the whole app**, so users without a plan will hit plan limits. Do this on purpose, together with the go-live.
- `.env.production.example` ships with both set to `false` (free-launch mode). Rebuild/restart the backend after changing the env.

No BTCPay server is needed for the live assets: `btc-onchain` is now direct-to-wallet; Lightning and LTC stay off.

### Assets (EVM)

| Asset id | Network (chain id) | Contract | Decimals | Confirmations (default) | Typical wait |
|---|---|---|---|---|---|
| `usdt-bep20` | BNB Smart Chain (56) | `0x55d398326f99059fF775485246999027B3197955` | 18 | 30 | ~14 s |
| `usdc-bep20` | BNB Smart Chain (56) | `0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d` | 18 | 30 | ~14 s |
| `usdt-polygon` | Polygon PoS (137) | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | 6 | 64 | ~2 min |
| `usdc-polygon` | Polygon PoS (137) | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` (native Circle USDC) | 6 | 64 | ~2 min |
| `usdt-erc20` | Ethereum (1) | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | 6 | 12 | ~2.4 min |
| `usdc-erc20` | Ethereum (1) | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | 6 | 12 | ~2.4 min |

Important details (all verified on-chain by `scripts/check_evm_live.py`):
- Decimals differ per chain: USDT and USDC on BSC use 18 decimals, on Polygon and Ethereum 6. The code uses each contract's own decimals.
- Polygon USDT is the canonical Tether token. It was upgraded in place to "USDT0" in August 2025 and kept the same address; the contract itself reports name/symbol `USDT0`. Some wallets show "USDT0"; the pay page tells the user it is the same token.
- Polygon USDC is Circle's native USDC (`0x3c49...`). The older bridged **USDC.e** (`0x2791...`) is deliberately NOT supported; a transfer of USDC.e is ignored and would have to be handled manually.

### Environment variables

| Env var | Default | Notes |
|---|---|---|
| `CRYPTO_EVM_ADDRESS` | none | The receiving address for all EVM chains. |
| `CRYPTO_LIVE_ASSETS` | all configured | Allowlist (above). |
| `CRYPTO_BSC_RPC_URLS`, `CRYPTO_POLYGON_RPC_URLS`, `CRYPTO_ETH_RPC_URLS` | built-in public lists | Comma-separated, tried in order with failover and a chain-id check. Put a private RPC first for reliability. |
| `CRYPTO_BSC_CONFIRMATIONS`, `CRYPTO_POLYGON_CONFIRMATIONS`, `CRYPTO_ETH_CONFIRMATIONS` | 30 / 64 / 12 | Per chain. `CRYPTO_CONFIRMATIONS` sets one value for all chains (a per-chain value wins over it). |
| `CRYPTO_OVERPAY_TOLERANCE_USDT` | 1 | A payment up to this much above the tagged amount is accepted; more goes to admin review. Used for USDT and USDC alike (1 USD). |
| `CRYPTO_WATCHER` / `CRYPTO_WATCH_SECONDS` | on / 20 | Background scanner. Pay-page polling also triggers a throttled scan. |
| `CRYPTO_INVOICE_MINUTES` | 30 | Payment window. A transfer arriving within 24 h after it is still matched (marked late). |
| `BILLING_ADMIN_ACCOUNTS` | none | Comma-separated account ids or emails that may use `/billing/admin/*`. Without it the admin routes return 403. |
| `APP_ENV=production` | | In production, simulated payments are refused. An asset that is not live is unavailable, so nobody can get a free plan. |

Default public RPCs (no API key; probed from the build box; each accepted a 1000-block `eth_getLogs`):
- BSC: bsc-rpc.publicnode.com, public-bsc.nownodes.io, rpc-bsc.48.club, bsc.rpc.blxrbdn.com, bsc.drpc.org (rate-limited, last resort).
- Polygon: polygon-bor-rpc.publicnode.com, gateway.tenderly.co/public/polygon, rpc-mainnet.matic.quiknode.pro.
- Ethereum: ethereum-rpc.publicnode.com, gateway.tenderly.co/public/mainnet, rpc.mevblocker.io, rpc.flashbots.net.
Public endpoints can rate-limit or disappear. The pool fails over automatically, but for a paid product put a private RPC first (a free tier of any provider is enough for this volume). Re-run the live check from the production server (Germany) after deploying.

### How scanning and matching work
- One `eth_getLogs` per (chain, token, address) per scan, only while an invoice for that asset is pending, in windows of at most 1000 blocks. In steady state that is one small request per active asset every 20 s, per chain independently; a chain that is down never blocks the others.
- The scan cursor is `head - confirmations`, persisted per chain+token+address. If the watcher was down, it catches up at most 20000 blocks on BSC (~2.5 h), 6000 on Polygon (~3.5 h) and 1500 on Ethereum (~5 h); older payments can be rescued with the tx-hash claim or admin confirm (a gap is recorded).
- Each invoice amount carries a unique tag (0.001 to 0.999) that is unique among open invoices of the SAME asset. Matching is per chain+token+address, so the same amount of another token or on another chain can never activate the wrong invoice, and duplicate detection is also scoped per chain+token.
- Zero-value transfers ("address poisoning") are ignored.
- Edge cases: underpaid never auto-activates (shown to the user, reviewed by admin); overpay within tolerance activates; larger overpay, ambiguous amount, or duplicate go to review; expired invoices can still be rescued by the user pasting the tx hash or by an admin.

## USDT on Tron (TRC20)

| Item | Value |
|---|---|
| Asset id | `usdt-trc20` |
| Receiving address | `CRYPTO_TRON_ADDRESS=TDuvB4k5foeTrUFFeDdnpCHVbn6M6QgSwf` (base58check verified) |
| Token contract | `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t` (hex `0xa614f803b6fd780986a42c78ec9c7f77e6ded13c`): name "Tether USD", symbol USDT, **6 decimals**, verified on-chain |
| Confirmations | 20 (`CRYPTO_TRON_CONFIRMATIONS`), about 1 minute |
| Max catch-up window | 6000 blocks (about 5 h) |

How it works: the watcher reads Tron through its Ethereum-compatible JSON-RPC (`/jsonrpc`): `eth_getLogs` for the USDT `Transfer` event filtered by your address as recipient (1000-block windows), and `eth_getTransactionReceipt` for the claim-by-txid. This is the same scan, tag, confirmation and claim logic as the EVM chains, scoped to `tron:<contract>:<address>`. Default endpoints (key-less, probed live): `https://api.trongrid.io/jsonrpc` and `https://tron-rpc.publicnode.com/jsonrpc`. Override/prepend with `CRYPTO_TRON_RPC_URLS` (comma list). TronGrid is rate-limited without a key; set the optional `TRONGRID_API_KEY` for production. Users paste the 64-hex transaction id (with or without 0x) in the claim box.

Fees: the sender pays Tron fees in TRX/energy; the pay page warns about it. Do not give the sender any instructions about Ethereum/BSC for this address: a Tron address is not an EVM address.

## Bitcoin on-chain

| Item | Value |
|---|---|
| Asset id | `btc-onchain` |
| Receiving address | `CRYPTO_BTC_ADDRESS=bc1qd3fyhu2a97hhgezd7sf7rk6h740w53xa6wwpd3` (native SegWit P2WPKH, bech32 checksum verified) |
| Detection | Esplora REST API, watch-only. Default endpoints: `https://mempool.space/api`, `https://blockstream.info/api` (failover). Prepend your own with `CRYPTO_BTC_API_URLS` (comma list) or `CRYPTO_BTC_API` (one base URL). |
| Confirmations | 3 (`CRYPTO_BTC_CONFIRMATIONS`), about 30 minutes or more |
| Amount | Satoshis. `amount_crypto` = plan USD / BTC price (rounded to sats) + a unique tag of 1 to 999 sats, unique among open BTC invoices. The untagged amount is also accepted if the wallet drops the tag. |
| Price | CoinGecko, then mempool.space `/api/v1/prices`, or fixed via `CRYPTO_RATES_JSON={"BTC":65000}`. **The offline reference price is never used for a live BTC invoice**: if no live price is available, creating the invoice fails with a clear error instead of quoting a wrong amount. The price is locked on the invoice (`rate_usd`) and shown to the user. |
| Overpay tolerance | `CRYPTO_OVERPAY_TOLERANCE_USDT` (default 1 USD) converted to sats **at the invoice's locked rate**. More than that goes to admin review. |
| Matching | One transaction output = one transfer (`txid:vout`). Unconfirmed transactions are shown to the user ("0 of 3") but never activate the plan. A replaced/evicted (RBF) transaction simply disappears. Coins moving from our own address (change/consolidation) are never a customer payment (review). |
| QR / URI | BIP-21 `bitcoin:<address>?amount=<btc>`; plus an address-only QR. |

Price-volatility policy: the BTC amount is fixed at invoice creation and the invoice lasts `CRYPTO_INVOICE_MINUTES` (30). The user pays that exact amount, so a move during the window costs/benefits the merchant, never causes a mismatch. A payment that arrives late (up to 24 h) is still accepted at the **locked** rate and flagged "late" in the admin view, so you bear that price risk; if BTC moved a lot, treat it via the admin review. Shorten `CRYPTO_INVOICE_MINUTES` to reduce the exposure.

Common failure to know: a wallet option "subtract fee from amount" sends less than invoiced: it is shown as underpaid and goes to review (the user pays the difference). The pay page tells users to pay fees on top.

### What is NOT live, and why
- **Native ETH and BNB**: never live (even if listed in `CRYPTO_LIVE_ASSETS`). The watcher only reads ERC-20 `Transfer` logs; detecting native transfers needs block/transaction scanning and an exact-amount match against a volatile price, which needs a trusted price feed plus tolerance that cannot be done safely with key-less public RPCs. Use the stablecoins.
- **Native TRX**: never live, same reason as ETH/BNB.
- **BTC Lightning and LTC**: need a BTCPay Server (`BTCPAY_*`); disabled and hidden. Not in `CRYPTO_LIVE_ASSETS`.
- **TON**: needs a TON address and its own detection; disabled and hidden.
In production none of these is offered to users unless live (hidden, not just disabled).

Admin endpoints (need `BILLING_ADMIN_ACCOUNTS`):
- `GET /api/v1/billing/admin/payments`: pending invoices plus transfers needing review.
- `POST /api/v1/billing/admin/invoices/{id}/confirm` with `{"tx": "0x…", "note": "why"}`: manual confirm; a tx is verified on-chain and the note is mandatory.

Read-only live checks (no payments, no keys): `python scripts/check_tron_btc_live.py` (Tron endpoints, USDT contract code/name/symbol/decimals, address balance, real log and receipt parsing; Bitcoin Esplora endpoints, tip height, real transaction parsing, live BTC price) and `python scripts/check_evm_live.py <your address>`. It verifies, per chain, endpoints, chain id and 1000-block `getLogs`; for each of the six contracts its code, name, symbol, decimals and balance; real-log parsing; and that the address is a normal wallet on each chain.

First real test (by the owner only, use small amounts, one per network): create a Pro 1-month invoice for an asset, send the exact tagged amount from your own wallet on the matching network (for example 15.xxx USDT on BEP20), and watch the status move to "detected N of M", then "paid". Repeat for Polygon, Tron (for example 15.xxx USDT TRC20; keep some TRX in the sending wallet) and Bitcoin (send the exact sats amount shown, in one transaction, fee on top; wait for "3 of 3"). Ethereum gas is expensive; test it once. Never send on a different network than the one shown on the invoice.
