import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_membership, require_admin
from app.db import get_db
from app.db.models import KnowledgeBase, Membership

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
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeBase]:
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.org_id == membership.org_id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(result.scalars().all())
