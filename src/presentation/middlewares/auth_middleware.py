from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.shared.config import get_settings

_settings = get_settings()

api_key_header = APIKeyHeader(name=_settings.api_key_header, auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

VALID_API_KEYS: set[str] = {_settings.api_key_value}


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=_settings.jwt_access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _settings.secret_key, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _settings.secret_key, algorithms=[_settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    api_key: str | None = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(http_bearer),
) -> dict:
    """Accept either API key or JWT bearer token."""
    if api_key and api_key in VALID_API_KEYS:
        return {"sub": "api-key-user", "auth_method": "api_key"}

    if bearer:
        return decode_access_token(bearer.credentials)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide API key or Bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
