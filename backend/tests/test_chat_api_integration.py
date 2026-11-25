"""阶段 6 端到端问答集成测试（mock LLM + 提取式降级，不调用外部模型）。

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
from app.db.models import (
    Document,
    DocumentChunk,
    KnowledgeBase,
    Membership,
    Organization,
    User,
)
from app.main import app

pytestmark = pytest.mark.integration


@dataclass
class ChatContext:
    org_id: uuid.UUID
    member_user_id: uuid.UUID
    granted_kb_id: uuid.UUID
    restricted_kb_id: uuid.UUID
    member_token: str
    member_email: str


def _run(coro):
    return asyncio.run(coro)


async def _create_context(unique: str) -> ChatContext:
    get_settings.cache_clear()
    async with AsyncSessionLocal() as s:
        org = Organization(name=f"chat-org-{unique}")
        s.add(org)
        await s.flush()

        admin = User(email=f"chat-admin-{unique}@example.com",
                     password_hash=hash_password("ChangeMe123!"))
        member = User(email=f"chat-member-{unique}@example.com",
                      password_hash=hash_password("ChangeMe123!"))
        s.add_all([admin, member])
        await s.flush()

        s.add(Membership(org_id=org.id, user_id=admin.id, role="admin"))
        s.add(Membership(org_id=org.id, user_id=member.id, role="member"))
        granted = KnowledgeBase(org_id=org.id, name=f"员工手册-{unique}", visibility="org")
        restricted = KnowledgeBase(org_id=org.id, name=f"薪酬-{unique}", visibility="restricted")
        s.add_all([granted, restricted])
        await s.flush()

        doc = Document(
            org_id=org.id, kb_id=granted.id,
            original_filename="manual.md", stored_key=f"{granted.id}/manual.md",
            file_format="markdown", size_bytes=1, content_hash=uuid.uuid4().hex,
            status="ready",
        )
        s.add(doc)
        await s.flush()

        s.add_all([
            DocumentChunk(document_id=doc.id, org_id=org.id, kb_id=granted.id,
                          chunk_index=0, content="员工每年享有五天年假。", locator={
                              "page_number": None, "section_path": ["员工手册", "年假"],
                              "char_start": 0, "char_end": 12}),
            DocumentChunk(document_id=doc.id, org_id=org.id, kb_id=granted.id,
                          chunk_index=1, content="加班需要提前一天提交审批。", locator={
                              "page_number": None, "section_path": ["员工手册", "加班"],
                              "char_start": 0, "char_end": 14}),
        ])
        await s.commit()

        get_settings.cache_clear()
        return ChatContext(
            org_id=org.id,
            member_user_id=member.id,
            granted_kb_id=granted.id,
            restricted_kb_id=restricted.id,
            member_token=create_access_token(str(member.id)),
            member_email=f"chat-member-{unique}@example.com",
        )


def _cleanup(org_id: uuid.UUID) -> None:
    async def _delete() -> None:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Organization).where(Organization.id == org_id))
            await s.commit()

    _run(_delete())


def test_ask_returns_cited_extractive_answer_and_refuses_irrelevant() -> None:
    unique = uuid.uuid4().hex[:12]
    ctx = _run(_create_context(unique))
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {ctx.member_token}"}

            resp = client.post("/chat/ask", json={
                "question": "年假有几天？",
                "kb_ids": [str(ctx.granted_kb_id)],
            }, headers=headers)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["status"] == "answered", body
            assert body["citations"], body
            assert any("S1" == c["label"] for c in body["citations"])

            resp2 = client.post("/chat/ask", json={
                "question": "今天天气怎么样？",
                "kb_ids": [str(ctx.granted_kb_id)],
            }, headers=headers)
            assert resp2.status_code == 200, resp2.text
            body2 = resp2.json()
            assert body2["status"] == "refused", body2
            assert body2["citations"] == []
    finally:
        _cleanup(ctx.org_id)


def test_ask_with_unauthorized_kb_does_not_leak() -> None:
    unique = uuid.uuid4().hex[:12]
    ctx = _run(_create_context(unique))
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {ctx.member_token}"}
            resp = client.post("/chat/ask", json={
                "question": "薪酬是多少？",
                "kb_ids": [str(ctx.restricted_kb_id)],
            }, headers=headers)
            assert resp.status_code == 404, resp.text
    finally:
        _cleanup(ctx.org_id)