"""接口层通用依赖。

阶段 2 先用“管理员负责建库和上传”这一条最简单授权规则；阶段 5 会替换为
统一的 access_scope，并覆盖普通员工的读取路径。
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import get_db
from app.db.models import Membership, User


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
    """仅管理员可执行建库和上传等写操作。"""
    if membership.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以执行此操作",
        )
    return membership
