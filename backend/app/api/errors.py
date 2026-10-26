"""API error envelope and exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.application.exceptions import ApplicationError


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        _request: Request, exc: ApplicationError
    ) -> JSONResponse:
        retry = exc.details.get("retry_after_seconds")
        return JSONResponse(
            status_code=exc.status_code,
            headers={"Retry-After": str(retry)} if retry else None,
            content=ErrorResponse(
                error=ErrorBody(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorBody(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details={"errors": exc.errors()},
                )
            ).model_dump(),
        )
