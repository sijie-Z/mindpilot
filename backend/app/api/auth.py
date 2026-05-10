"""
Authentication API - login, register, token management.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import TokenData, auth_handler, get_current_user
from app.core.audit import log_action
from app.storage.database import get_db_session

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    return pwd_context.verify(password, hashed)


class UserLogin(BaseModel):
    username: str
    password: str


class UserRegister(BaseModel):
    username: str
    password: str
    email: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str




@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, request: Request):
    """Login with username and password."""
    ip = request.client.host if request.client else None
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, username, email, role, password_hash FROM users WHERE username=:username"),
            {"username": data.username}
        )
        user = result.fetchone()

        if not user:
            await log_action(action="login_failed", detail=f"username={data.username}", ip_address=ip)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        user_id, username, _email, role, password_hash = user[0], user[1], user[2], user[3], user[4]

        if not verify_password(data.password, password_hash or ""):
            await log_action(user_id=user_id, username=username, action="login_failed", detail="wrong password", ip_address=ip)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Create token
        token = auth_handler.create_access_token({
            "sub": user_id,
            "username": username,
            "role": role or "user",
        })

        await log_action(user_id=user_id, username=username, action="login", ip_address=ip)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=user_id,
            username=username,
        )


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, request: Request):
    """Register a new user."""
    ip = request.client.host if request.client else None
    async with get_db_session() as db:
        # Check if username exists
        result = await db.execute(
            text("SELECT id FROM users WHERE username=:username"),
            {"username": data.username}
        )
        if result.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Create user
        user_id = str(uuid.uuid4())
        password_hash = hash_password(data.password)

        await db.execute(
            text("INSERT INTO users (id, username, email, role, password_hash) "
                 "VALUES (:id, :username, :email, 'user', :hash)"),
            {"id": user_id, "username": data.username, "email": data.email or None, "hash": password_hash}
        )

        # Create token
        token = auth_handler.create_access_token({
            "sub": user_id,
            "username": data.username,
            "role": "user",
        })

        await log_action(user_id=user_id, username=data.username, action="register", ip_address=ip)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=user_id,
            username=data.username,
        )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: TokenData = Depends(get_current_user)):
    """Get current user info."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT id, username, email, role FROM users WHERE id=:user_id"),
            {"user_id": current_user.user_id}
        )
        user = result.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserResponse(
            id=user[0],
            username=user[1],
            email=user[2] or "",
            role=user[3] or "user",
        )


@router.post("/refresh")
async def refresh_token(current_user: TokenData = Depends(get_current_user)):
    """Refresh the access token."""
    token = auth_handler.create_access_token({
        "sub": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
    })
    return {"access_token": token, "token_type": "bearer"}


@router.get("/api-keys")
async def list_api_keys(current_user: TokenData = Depends(get_current_user)):
    """List API keys for the current user."""
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT api_key FROM users WHERE id=:user_id"),
            {"user_id": current_user.user_id}
        )
        user = result.fetchone()
        return {
            "api_key": user[0] if user and user[0] else None,
            "has_key": bool(user and user[0]),
        }


@router.post("/api-keys/generate")
async def generate_api_key(current_user: TokenData = Depends(get_current_user)):
    """Generate a new API key."""
    new_key = auth_handler.generate_api_key()
    key_hash = auth_handler.hash_api_key(new_key)

    async with get_db_session() as db:
        await db.execute(
            text("UPDATE users SET api_key=:hash WHERE id=:user_id"),
            {"hash": key_hash, "user_id": current_user.user_id}
        )

    return {
        "api_key": new_key,
        "warning": "This key will only be shown once. Store it securely.",
    }
