"""Integration REST endpoints — /api/v1/integrations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_integration_service
from app.api.schemas.integration import IntegrationRequestBody, IntegrationResultResponse
from app.application.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/adapters", response_model=list[IntegrationResultResponse])
def list_integration_adapters(
    integration_service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> list[IntegrationResultResponse]:
    return [
        IntegrationResultResponse.from_domain(result)
        for result in integration_service.list_adapters()
    ]


@router.post("/execute", response_model=IntegrationResultResponse)
def execute_integration(
    body: IntegrationRequestBody,
    integration_service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationResultResponse:
    result = integration_service.execute(body.to_domain())
    return IntegrationResultResponse.from_domain(result)
