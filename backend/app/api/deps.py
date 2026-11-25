"""接口层通用依赖。"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import get_db
from app.db.models import Membership, User
from app.services.access import AccessScope, build_access_scope


async def get_current_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Membership:
    """取当前用户的组织成员关系。第一版约定每个用户属于一个组织。"""
    stmt = (
        select(Membership)
        .where(Membership.user_id == user.id)
        .order_by(Membership.created_at)
        .limit(1)
    )
    membership = (await db.execute(stmt)).scalars().first()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户不属于任何组织",
        )
    return membership


async def require_admin(
    membership: Membership = Depends(get_current_membership),
) -> Membership:
    """仅管理员可执行建库、上传和授权等写操作。"""
    if membership.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以执行此操作",
        )
    return membership


async def get_access_scope(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> AccessScope:
    """统一权限范围：所有读取入口都依赖它，在查询前过滤。"""
    return await build_access_scope(db, membership)