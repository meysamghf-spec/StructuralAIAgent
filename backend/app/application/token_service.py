"""Signed bearer tokens for authenticated API access."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID


class TokenValidationError(ValueError):
    pass


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_access_token(
    *,
    secret: str,
    account_id: str,
    user_id: UUID,
    email: str,
    display_name: str | None,
    expires_in_hours: int,
) -> str:
    header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)
    payload = {
        "sub": str(user_id),
        "account_id": account_id,
        "email": email,
        "display_name": display_name,
        "exp": int(expires_at.timestamp()),
    }
    payload_segment = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload_segment}".encode()
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload_segment}.{_b64_encode(signature)}"


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    if not token.strip():
        raise TokenValidationError("Malformed access token")

    try:
        header_segment, payload_segment, signature_segment = token.split(".", 2)
    except ValueError as exc:
        raise TokenValidationError("Malformed access token") from exc

    try:
        header = json.loads(_b64_decode(header_segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise TokenValidationError("Malformed access token header") from exc

    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise TokenValidationError("Unsupported access token algorithm")

    signing_input = f"{header_segment}.{payload_segment}".encode()
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual = _b64_decode(signature_segment)
    except ValueError as exc:
        raise TokenValidationError("Malformed access token signature") from exc
    if not hmac.compare_digest(expected, actual):
        raise TokenValidationError("Invalid access token signature")

    try:
        payload = json.loads(_b64_decode(payload_segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise TokenValidationError("Malformed access token payload") from exc

    sub = payload.get("sub")
    account_id = payload.get("account_id")
    if not isinstance(sub, str) or not sub.strip():
        raise TokenValidationError("Access token subject is missing")
    if not isinstance(account_id, str) or not account_id.strip():
        raise TokenValidationError("Access token account is missing")

    exp = payload.get("exp")
    if not isinstance(exp, int) or datetime.now(UTC).timestamp() >= exp:
        raise TokenValidationError("Access token expired")
    return payload
