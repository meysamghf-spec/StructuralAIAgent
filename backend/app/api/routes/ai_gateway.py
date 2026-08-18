"""AI Gateway REST endpoints — /api/v1/ai."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_ai_gateway_service
from app.api.schemas.ai_gateway import AICompletionRequestBody, AICompletionResponseBody
from app.application.ai_gateway_service import AIGatewayService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/providers")
def list_ai_providers(
    ai_gateway: Annotated[AIGatewayService, Depends(get_ai_gateway_service)],
) -> dict[str, list[str]]:
    return {"providers": ai_gateway.list_providers()}


@router.post("/complete", response_model=AICompletionResponseBody)
def complete_ai_request(
    body: AICompletionRequestBody,
    ai_gateway: Annotated[AIGatewayService, Depends(get_ai_gateway_service)],
) -> AICompletionResponseBody:
    response = ai_gateway.complete(body.to_domain(), provider_kind=body.provider)
    return AICompletionResponseBody.from_domain(response)
