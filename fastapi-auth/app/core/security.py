"""真实的安全层：Argon2 密码哈希 + JWT 签发/验证 + get_current_user 依赖。"""
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

pwd_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(raw_password: str) -> str:
    """用 Argon2 生成密码哈希。"""
    return pwd_hasher.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """校验明文密码是否匹配 Argon2 哈希；任何失败都返回 False。"""
    try:
        return pwd_hasher.verify(hashed_password, raw_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(subject: str) -> str:
    """签发带过期时间的 JWT，subject 放用户名。"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "iat": now, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """依赖：解析 Bearer JWT 并返回数据库里的用户，失败抛 401。"""
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
        username: str | None = payload.get("sub")
        if not username:
            raise unauthorized
    except jwt.PyJWTError:
        raise unauthorized

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise unauthorized
    return user
