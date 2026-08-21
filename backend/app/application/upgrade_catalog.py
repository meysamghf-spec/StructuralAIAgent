"""In-memory upgrade product catalog."""

from __future__ import annotations

from app.application.exceptions import UpgradeProductNotFoundError
from app.domain.models.payments import SupportedCryptoOption, UpgradeProduct

UPGRADE_PRODUCTS: dict[str, UpgradeProduct] = {
    "pro-workspace": UpgradeProduct(
        id="pro-workspace",
        name="Pro Workspace",
        description="Unlock advanced analysis, design, and optimization workflows.",
        fiat_price_usd=49.0,
        billing_period_days=30,
        features=[
            "Multi-member optimization",
            "Validated solver result ingestion",
            "Extended traceability exports",
        ],
    ),
    "solver-plus": UpgradeProduct(
        id="solver-plus",
        name="Solver Plus",
        description="Priority CSI integration and expanded result categories.",
        fiat_price_usd=99.0,
        billing_period_days=365,
        features=[
            "ETABS / SAP2000 / SAFE extraction",
            "Results workspace analytics",
            "CAD plan generation bundle",
        ],
    ),
}

SUPPORTED_CRYPTO_OPTIONS: list[SupportedCryptoOption] = [
    SupportedCryptoOption(
        currency="BTC",
        network="bitcoin",
        display_name="Bitcoin",
        required_confirmations=3,
        decimals=8,
    ),
    SupportedCryptoOption(
        currency="ETH",
        network="ethereum",
        display_name="Ethereum",
        required_confirmations=3,
        decimals=8,
    ),
    SupportedCryptoOption(
        currency="USDT",
        network="ethereum",
        display_name="Tether (ERC-20)",
        required_confirmations=3,
        decimals=6,
    ),
]


def list_upgrade_products() -> list[UpgradeProduct]:
    return sorted(UPGRADE_PRODUCTS.values(), key=lambda item: item.id)


def get_upgrade_product(product_id: str) -> UpgradeProduct:
    product = UPGRADE_PRODUCTS.get(product_id)
    if product is None:
        raise UpgradeProductNotFoundError(product_id)
    return product


def get_crypto_option(currency: str, network: str) -> SupportedCryptoOption:
    for option in SUPPORTED_CRYPTO_OPTIONS:
        if option.currency.upper() == currency.upper() and option.network.lower() == network.lower():
            return option
    from app.application.exceptions import UnsupportedPaymentNetworkError

    raise UnsupportedPaymentNetworkError(currency, network)
