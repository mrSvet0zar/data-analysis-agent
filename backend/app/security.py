"""Optional bearer-token auth.

If ``API_AUTH_TOKEN`` is unset (local dev), the API is open. If set, callers must
send ``Authorization: Bearer <token>`` or ``X-API-Key: <token>``. Uses a
constant-time comparison to avoid leaking the token via timing.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def _extract(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def require_auth(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    if not settings.auth_enabled:
        return
    token = _extract(authorization, x_api_key)
    if not token or not secrets.compare_digest(token, settings.api_auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
