import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.db.models import User

pwd_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(raw_password: str) -> str:
    """Argon2 哈希，只保存不可逆哈希。"""
    return pwd_hasher.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """校验密码；哈希损坏或密码不匹配都返回 False。"""
    try:
        return pwd_hasher.verify(hashed_password, raw_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(subject: str) -> str:
    """签发带过期时间的 JWT，subject 放用户 UUID。"""
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "iat": now, "exp": expires}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """依赖：解析 Bearer JWT 并从数据库取回当前用户，失败抛 401。"""
    settings = get_settings()
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except jwt.PyJWTError:
        raise unauthorized

    subject = payload.get("sub")
    if not subject:
        raise unauthorized

    try:
        user_id = uuid.UUID(subject)
    except (ValueError, TypeError):
        raise unauthorized

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise unauthorized
    return user
