import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_access_scope, require_admin
from app.db import get_db
from app.db.models import (
    KnowledgeBase,
    KnowledgeBasePermission,
    Membership,
    User,
)
from app.services.access import AccessScope

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    visibility: Literal["org", "restricted"] = Field(
        default="org", description="org 组织内可见；restricted 需要显式授权"
    )


class KnowledgeBaseOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    visibility: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionGrant(BaseModel):
    user_email: str = Field(..., description="要授权读取的成员邮箱")
    access_level: Literal["read"] = "read"


class PermissionOut(BaseModel):
    kb_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    access_level: str
    created_at: datetime


def _require_kb_read(scope: AccessScope, kb_id: uuid.UUID) -> None:
    if not scope.can_read(kb_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )


async def _get_org_user(db: AsyncSession, org_id: uuid.UUID, email: str) -> User:
    result = await db.execute(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.org_id == org_id, User.email == email)
    )
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织内不存在该成员",
        )
    return user


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    admin: Membership = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBase:
    existing = (
        await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.org_id == admin.org_id,
                KnowledgeBase.name == payload.name,
            )
        )
    ).scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同一组织内知识库名称已存在",
        )

    kb = KnowledgeBase(
        org_id=admin.org_id,
        name=payload.name,
        visibility=payload.visibility,
    )
    db.add(kb)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同一组织内知识库名称已存在",
        )
    await db.refresh(kb)
    return kb


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeBase]:
    if not scope.readable_kb_ids:
        return []
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.id.in_(scope.readable_kb_ids))
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBase:
    _require_kb_read(scope, kb_id)
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    return kb


@router.get("/{kb_id}/permissions", response_model=list[PermissionOut])
async def list_permissions(
    kb_id: uuid.UUID,
    admin: Membership = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.org_id != admin.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")

    result = await db.execute(
        select(KnowledgeBasePermission, User.email)
        .join(User, User.id == KnowledgeBasePermission.user_id)
        .where(KnowledgeBasePermission.kb_id == kb_id)
        .order_by(KnowledgeBasePermission.created_at)
    )
    return [
        {
            "kb_id": row[0].kb_id,
            "user_id": row[0].user_id,
            "email": row.email,
            "access_level": row[0].access_level,
            "created_at": row[0].created_at,
        }
        for row in result.all()
    ]


@router.put("/{kb_id}/permissions", response_model=PermissionOut, status_code=status.HTTP_201_CREATED)
async def grant_permission(
    kb_id: uuid.UUID,
    payload: PermissionGrant,
    admin: Membership = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.org_id != admin.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")

    user = await _get_org_user(db, admin.org_id, payload.user_email)
    permission = KnowledgeBasePermission(
        kb_id=kb_id,
        user_id=user.id,
        access_level=payload.access_level,
    )
    db.add(permission)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.get(KnowledgeBasePermission, (kb_id, user.id))
        return {
            "kb_id": kb_id,
            "user_id": user.id,
            "email": payload.user_email,
            "access_level": existing.access_level if existing else payload.access_level,
            "created_at": existing.created_at if existing else datetime.now(),
        }
    await db.refresh(permission)
    return {
        "kb_id": permission.kb_id,
        "user_id": permission.user_id,
        "email": payload.user_email,
        "access_level": permission.access_level,
        "created_at": permission.created_at,
    }


@router.delete("/{kb_id}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: Membership = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.org_id != admin.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")

    permission = await db.get(KnowledgeBasePermission, (kb_id, user_id))
    if permission is not None:
        await db.delete(permission)
        await db.commit()