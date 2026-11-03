"""API Authentication and project-level authorization dependency."""

from typing import Optional
from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(x_api_key: Optional[str] = Security(api_key_header)) -> bool:
    """Verify incoming API key header against configured API_AUTH_KEY."""
    settings = get_settings()
    configured_key = settings.API_AUTH_KEY

    # If no key configured, permit access (development mode)
    if not configured_key:
        return True

    if not x_api_key or x_api_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key in 'X-API-Key' header",
        )
    return True

