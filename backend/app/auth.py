"""
Authentication utilities - JWT + API Key.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    user_id: str | None = None
    username: str | None = None
    role: str = "user"


class AuthHandler:
    """Handles JWT and API Key authentication."""

    def __init__(self):
        self.secret_key = settings.SECRET_KEY or "mindpilot-secret-change-me"
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60 * 24  # 24 hours

    def create_access_token(
        self,
        data: dict,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> TokenData:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("sub")
            username = payload.get("username")
            role = payload.get("role", "user")
            return TokenData(user_id=user_id, username=username, role=role)
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def generate_api_key(self) -> str:
        """Generate a new API key."""
        return secrets.token_urlsafe(32)


# Global auth handler
auth_handler = AuthHandler()


# Dependency functions
async def get_current_user(
    bearer: str | None = Security(bearer_scheme),
) -> TokenData:
    """FastAPI dependency to get current user from JWT token."""
    if not bearer:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = bearer.credentials
    return auth_handler.verify_token(token)


async def get_optional_user(
    bearer: str | None = Security(bearer_scheme),
) -> TokenData | None:
    """FastAPI dependency for optional authentication."""
    if not bearer:
        return None
    try:
        return auth_handler.verify_token(bearer.credentials)
    except HTTPException:
        return None


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> TokenData:
    """FastAPI dependency to verify API key."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key not provided",
        )

    # Check against configured API key
    if api_key == settings.API_KEY:
        return TokenData(user_id="api_user", username="api", role="admin")

    raise HTTPException(
        status_code=401,
        detail="Invalid API key",
    )


def require_role(required_role: str):
    """Dependency factory for role-based access control."""
    async def check_role(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role != required_role and user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail=f"Role '{required_role}' required",
            )
        return user
    return check_role


# Login endpoint helpers
def create_user_token(user_id: str, username: str, role: str = "user") -> str:
    """Create an access token for a user."""
    return auth_handler.create_access_token({
        "sub": user_id,
        "username": username,
        "role": role,
    })
