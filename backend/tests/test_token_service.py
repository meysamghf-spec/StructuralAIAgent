"""Unit tests for signed bearer token validation."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest

from app.application.token_service import TokenValidationError, create_access_token, decode_access_token


def _segment(value: dict[str, str]) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def test_decode_rejects_tampered_signature() -> None:
    user_id = uuid4()
    token = create_access_token(
        secret="test-secret",
        account_id=str(user_id),
        user_id=user_id,
        email="user@example.com",
        display_name=None,
        expires_in_hours=1,
    )
    header, payload, _signature = token.split(".")
    with pytest.raises(TokenValidationError, match="signature"):
        decode_access_token(f"{header}.{payload}.invalid", secret="test-secret")


def test_decode_rejects_unsupported_algorithm() -> None:
    user_id = uuid4()
    token = create_access_token(
        secret="test-secret",
        account_id=str(user_id),
        user_id=user_id,
        email="user@example.com",
        display_name=None,
        expires_in_hours=1,
    )
    parts = token.split(".")
    bad_header = _segment({"alg": "HS512", "typ": "JWT"})
    with pytest.raises(TokenValidationError, match="algorithm"):
        decode_access_token(f"{bad_header}.{parts[1]}.{parts[2]}", secret="test-secret")
