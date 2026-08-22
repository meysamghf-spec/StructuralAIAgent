"""Hybrid orchestration REST endpoints — /api/v1/orchestration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_entitlement_authorization_service,
    get_hybrid_orchestration_service,
    get_current_account,
    get_project_access_service,
)
from app.api.schemas.orchestration import OrchestrationResultResponse, OrchestrationTaskRequest
from app.application.entitlement_authorization_service import EntitlementAuthorizationService
from app.application.feature_requirements import optimization_requires_paid_entitlement
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.project_access_service import ProjectAccessService
from app.domain.models.platform_features import PlatformFeature
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.post("/execute", response_model=OrchestrationResultResponse)
def execute_orchestration_task(
    body: OrchestrationTaskRequest,
    orchestration_service: Annotated[
        HybridOrchestrationService, Depends(get_hybrid_orchestration_service)
    ],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    entitlements: Annotated[
        EntitlementAuthorizationService, Depends(get_entitlement_authorization_service)
    ],
) -> OrchestrationResultResponse:
    if body.project_id is not None:
        access.require_project(body.project_id, account)
    if body.task_type == "engineering.optimization.run":
        payload = body.payload or {}
        parameters = payload.get("parameters", {}) if isinstance(payload, dict) else {}
        if optimization_requires_paid_entitlement(parameters):
            entitlements.require_feature(
                account.account_id,
                PlatformFeature.MULTI_MEMBER_OPTIMIZATION,
            )
    result = orchestration_service.execute(body.to_domain())
    return OrchestrationResultResponse.from_domain(result)
