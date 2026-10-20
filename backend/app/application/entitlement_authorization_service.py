"""Backend-authoritative upgrade entitlement checks for platform features."""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.exceptions import FeatureAccessDeniedError
from app.application.upgrade_catalog import get_upgrade_product
from app.domain.models.payments import EntitlementStatus, UpgradeEntitlement
from app.domain.models.platform_features import FEATURE_UPGRADE_PRODUCT, PlatformFeature
from app.infrastructure.config import get_settings
from app.infrastructure.repositories.postgres_payment_repository import PostgresPaymentRepository


class EntitlementAuthorizationService:
    def __init__(self, repository: PostgresPaymentRepository | None = None) -> None:
        self._repo = repository or PostgresPaymentRepository()

    @property
    def enforcement_enabled(self) -> bool:
        settings = get_settings()
        return settings.entitlement_enforcement_enabled and settings.payments_enabled

    def require_feature(self, account_id: str, feature: PlatformFeature) -> None:
        if not self.enforcement_enabled:
            return
        if self.has_feature(account_id, feature):
            return
        product_id = FEATURE_UPGRADE_PRODUCT.get(feature)
        raise FeatureAccessDeniedError(feature.value, upgrade_product_id=product_id)

    def has_feature(self, account_id: str, feature: PlatformFeature) -> bool:
        product_id = FEATURE_UPGRADE_PRODUCT.get(feature)
        if product_id is None:
            return True
        entitlement = self._repo.get_active_entitlement(account_id, product_id)
        return self._is_usable(entitlement)

    def summarize_account_features(self, account_id: str) -> dict[str, dict[str, object]]:
        summary: dict[str, dict[str, object]] = {}
        for feature, product_id in FEATURE_UPGRADE_PRODUCT.items():
            if product_id is None:
                summary[feature.value] = {
                    "available": True,
                    "reason": "included",
                    "upgrade_product_id": None,
                }
                continue
            active = self._repo.get_active_entitlement(account_id, product_id)
            usable = self._is_usable(active)
            latest = active or self._latest_entitlement(account_id, product_id)
            reason = "active_entitlement" if usable else self._denial_reason(latest)
            summary[feature.value] = {
                "available": usable,
                "reason": reason,
                "upgrade_product_id": product_id,
                "product_name": get_upgrade_product(product_id).name,
                "entitlement_status": latest.status.value if latest else None,
                "expires_at": latest.expires_at.isoformat() if latest and latest.expires_at else None,
            }
        return summary

    def _latest_entitlement(
        self,
        account_id: str,
        upgrade_product_id: str,
    ) -> UpgradeEntitlement | None:
        for entitlement in self._repo.list_entitlements_for_account(account_id):
            if entitlement.upgrade_product_id == upgrade_product_id:
                return entitlement
        return None

    @staticmethod
    def _is_usable(entitlement: UpgradeEntitlement | None) -> bool:
        if entitlement is None:
            return False
        if entitlement.status != EntitlementStatus.ACTIVE:
            return False
        if entitlement.expires_at is not None and entitlement.expires_at <= datetime.now(UTC):
            return False
        return True

    @staticmethod
    def _denial_reason(entitlement: UpgradeEntitlement | None) -> str:
        if entitlement is None:
            return "no_entitlement"
        if entitlement.status == EntitlementStatus.EXPIRED:
            return "expired"
        if entitlement.status == EntitlementStatus.REVOKED:
            return "revoked"
        if entitlement.status == EntitlementStatus.PENDING:
            return "pending"
        if entitlement.expires_at is not None and entitlement.expires_at <= datetime.now(UTC):
            return "expired"
        return "inactive"
