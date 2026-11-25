"""阶段 5 权限模型：统一的 access_scope。

所有读取入口都必须先拿到当前用户可读知识库集合，再在数据库查询前应用过滤。
admin 可读本组织全部知识库；member 只能读 org 可见知识库 + 显式 read 授权。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBase, KnowledgeBasePermission, Membership


@dataclass(frozen=True)
class AccessScope:
    org_id: uuid.UUID
    role: str
    readable_kb_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)

    def can_read(self, kb_id: uuid.UUID) -> bool:
        return kb_id in self.readable_kb_ids


async def build_access_scope(
    db: AsyncSession, membership: Membership
) -> AccessScope:
    """返回当前用户可读的 kb_id 集合；admin 默认全量。"""
    if membership.role == "admin":
        result = await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.org_id == membership.org_id)
        )
        ids = {row[0] for row in result.all()}
        return AccessScope(
            org_id=membership.org_id,
            role=membership.role,
            readable_kb_ids=frozenset(ids),
        )

    org_visible = await db.execute(
        select(KnowledgeBase.id).where(
            KnowledgeBase.org_id == membership.org_id,
            KnowledgeBase.visibility == "org",
        )
    )
    granted = await db.execute(
        select(KnowledgeBasePermission.kb_id).where(
            KnowledgeBasePermission.user_id == membership.user_id
        )
    )
    ids = {row[0] for row in org_visible.all()} | {row[0] for row in granted.all()}
    return AccessScope(
        org_id=membership.org_id,
        role=membership.role,
        readable_kb_ids=frozenset(ids),
    )