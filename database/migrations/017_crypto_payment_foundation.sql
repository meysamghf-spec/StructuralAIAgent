-- Crypto payment and upgrade entitlement foundation

CREATE TABLE IF NOT EXISTS crypto_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(255) NOT NULL,
    upgrade_product_id VARCHAR(64) NOT NULL,
    invoice_id VARCHAR(64) NOT NULL UNIQUE,
    currency VARCHAR(16) NOT NULL,
    network VARCHAR(32) NOT NULL,
    fiat_amount_usd NUMERIC(12, 2) NOT NULL,
    crypto_amount NUMERIC(24, 12) NOT NULL,
    received_amount NUMERIC(24, 12),
    payment_address VARCHAR(255) NOT NULL,
    payment_uri TEXT,
    transaction_hash VARCHAR(255),
    required_confirmations INTEGER NOT NULL DEFAULT 3,
    current_confirmations INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    exchange_rate_source VARCHAR(64),
    exchange_rate NUMERIC(24, 12),
    exchange_rate_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    paid_at TIMESTAMPTZ,
    verified_at TIMESTAMPTZ,
    idempotency_key VARCHAR(128),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crypto_payments_account_id ON crypto_payments(account_id);
CREATE INDEX IF NOT EXISTS idx_crypto_payments_status ON crypto_payments(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_payments_tx_network
    ON crypto_payments(transaction_hash, network)
    WHERE transaction_hash IS NOT NULL
      AND status IN ('PAID', 'CONFIRMING', 'PAYMENT_DETECTED', 'OVERPAID', 'UNDERPAID');

CREATE TABLE IF NOT EXISTS upgrade_entitlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(255) NOT NULL,
    upgrade_product_id VARCHAR(64) NOT NULL,
    payment_id UUID NOT NULL REFERENCES crypto_payments(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL,
    activated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_upgrade_entitlements_account_id ON upgrade_entitlements(account_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_upgrade_entitlements_active_product
    ON upgrade_entitlements(account_id, upgrade_product_id)
    WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS payment_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES crypto_payments(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_audit_events_payment_id ON payment_audit_events(payment_id);

INSERT INTO schema_migrations (version, name)
VALUES ('017', 'crypto_payment_foundation')
ON CONFLICT (version) DO NOTHING;
