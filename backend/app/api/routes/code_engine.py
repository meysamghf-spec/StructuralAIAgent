"""CodeEngine REST endpoints — /api/v1/codes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_code_engine_service, get_current_account
from app.api.schemas.code_engine import (
    CodeCheckResponse,
    CodeConfigurationValidationResponse,
    CodeDefaultsEnvelopeResponse,
    RunCodeCheckRequest,
    StandardInfoResponse,
    ValidateCodeConfigurationRequest,
)
from app.application.code_engine_service import CodeEngineService
from app.domain.models.pem import Jurisdiction
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/codes", tags=["codes"])


@router.get("/standards", response_model=list[StandardInfoResponse])
def list_standards(
    code_engine: Annotated[CodeEngineService, Depends(get_code_engine_service)],
    _: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> list[StandardInfoResponse]:
    return [
        StandardInfoResponse.from_domain(item)
        for item in code_engine.list_available_standards()
    ]


@router.get("/defaults", response_model=CodeDefaultsEnvelopeResponse)
def get_code_defaults(
    code_engine: Annotated[CodeEngineService, Depends(get_code_engine_service)],
    _: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    jurisdiction: Jurisdiction = Query(default=Jurisdiction.IRAN),
) -> CodeDefaultsEnvelopeResponse:
    return CodeDefaultsEnvelopeResponse.from_domain(code_engine.get_defaults(jurisdiction))


@router.post("/validate", response_model=CodeConfigurationValidationResponse)
def validate_code_configuration(
    body: ValidateCodeConfigurationRequest,
    code_engine: Annotated[CodeEngineService, Depends(get_code_engine_service)],
    _: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> CodeConfigurationValidationResponse:
    result = code_engine.validate_configuration(body.configuration)
    return CodeConfigurationValidationResponse.from_domain(result)


@router.post("/checks/run", response_model=CodeCheckResponse)
def run_code_check(
    body: RunCodeCheckRequest,
    code_engine: Annotated[CodeEngineService, Depends(get_code_engine_service)],
    _: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> CodeCheckResponse:
    result = code_engine.run_check(
        body.plugin_id,
        body.check_id,
        body.inputs,
        code_configuration=body.code_configuration,
    )
    return CodeCheckResponse.from_domain(result)
