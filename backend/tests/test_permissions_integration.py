"""阶段 5 权限隔离集成测试：跨用户、跨知识库授权与越权 404。

需要本机 PostgreSQL：pytest -m integration
"""
import asyncio
import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db import AsyncSessionLocal
from app.db.models import KnowledgeBase, Membership, Organization, User
from app.main import app

pytestmark = pytest.mark.integration


@dataclass
class PermissionContext:
    org_id: uuid.UUID
    admin_user_id: uuid.UUID
    member_user_id: uuid.UUID
    org_kb_id: uuid.UUID
    restricted_kb_id: uuid.UUID
    admin_token: str
    member_token: str


def _run(coro):
    return asyncio.run(coro)


async def _create_context(unique: str) -> PermissionContext:
    get_settings.cache_clear()
    async with AsyncSessionLocal() as s:
        org = Organization(name=f"perm-org-{unique}")
        s.add(org)
        await s.flush()

        admin = User(email=f"perm-admin-{unique}@example.com",
                     password_hash=hash_password("ChangeMe123!"))
        member = User(email=f"perm-member-{unique}@example.com",
                      password_hash=hash_password("ChangeMe123!"))
        s.add_all([admin, member])
        await s.flush()

        s.add(Membership(org_id=org.id, user_id=admin.id, role="admin"))
        s.add(Membership(org_id=org.id, user_id=member.id, role="member"))
        org_kb = KnowledgeBase(org_id=org.id, name=f"公开手册-{unique}", visibility="org")
        restricted_kb = KnowledgeBase(org_id=org.id, name=f"薪酬保密-{unique}", visibility="restricted")
        s.add_all([org_kb, restricted_kb])
        await s.commit()

        get_settings.cache_clear()
        return PermissionContext(
            org_id=org.id,
            admin_user_id=admin.id,
            member_user_id=member.id,
            org_kb_id=org_kb.id,
            restricted_kb_id=restricted_kb.id,
            admin_token=create_access_token(str(admin.id)),
            member_token=create_access_token(str(member.id)),
        )


def _cleanup(org_id: uuid.UUID) -> None:
    async def _delete() -> None:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Organization).where(Organization.id == org_id))
            await s.commit()

    _run(_delete())


def test_member_sees_only_granted_kbs() -> None:
    unique = uuid.uuid4().hex[:12]
    ctx = _run(_create_context(unique))
    try:
        with TestClient(app) as client:
            resp = client.get("/knowledge-bases",
                              headers={"Authorization": f"Bearer {ctx.member_token}"})
            assert resp.status_code == 200, resp.text
            ids = {item["id"] for item in resp.json()}
            assert str(ctx.org_kb_id) in ids
            assert str(ctx.restricted_kb_id) not in ids
    finally:
        _cleanup(ctx.org_id)


def test_member_direct_restricted_kb_returns_404() -> None:
    unique = uuid.uuid4().hex[:12]
    ctx = _run(_create_context(unique))
    try:
        with TestClient(app) as client:
            resp = client.get(f"/knowledge-bases/{ctx.restricted_kb_id}",
                              headers={"Authorization": f"Bearer {ctx.member_token}"})
            assert resp.status_code == 404, resp.text
    finally:
        _cleanup(ctx.org_id)


def test_grant_revokes_and_citation_snapshot_scope() -> None:
    unique = uuid.uuid4().hex[:12]
    ctx = _run(_create_context(unique))
    try:
        with TestClient(app) as client:
            admin_headers = {"Authorization": f"Bearer {ctx.admin_token}"}
            member_headers = {"Authorization": f"Bearer {ctx.member_token}"}

            # 管理员给员工授权
            resp = client.put(
                f"/knowledge-bases/{ctx.restricted_kb_id}/permissions",
                json={"user_email": f"perm-member-{unique}@example.com", "access_level": "read"},
                headers=admin_headers,
            )
            assert resp.status_code == 201, resp.text

            resp = client.get("/knowledge-bases", headers=member_headers)
            ids = {item["id"] for item in resp.json()}
            assert str(ctx.restricted_kb_id) in ids

            # 收回授权后重新不可见
            resp = client.delete(
                f"/knowledge-bases/{ctx.restricted_kb_id}/permissions/{ctx.member_user_id}",
                headers=admin_headers,
            )
            assert resp.status_code == 204, resp.text

            resp = client.get("/knowledge-bases", headers=member_headers)
            ids = {item["id"] for item in resp.json()}
            assert str(ctx.restricted_kb_id) not in ids
    finally:
        _cleanup(ctx.org_id)