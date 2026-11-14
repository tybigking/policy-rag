"""上传接口集成测试：走真实 FastAPI + 本机 PostgreSQL，并在临时目录落盘。

默认 `pytest` 不运行本文件（见 pyproject addopts）；
运行方式：`pytest -m integration`，需要本机数据库已启动。
"""

import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path

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
class IntegrationContext:
    org_id: uuid.UUID
    user_id: uuid.UUID
    kb_id: uuid.UUID
    token: str


def _run(coro):
    return asyncio.run(coro)


async def _create_context(unique: str) -> IntegrationContext:
    async with AsyncSessionLocal() as s:
        org = Organization(name=f"it-org-{unique}")
        s.add(org)
        await s.flush()

        user = User(
            email=f"admin-{unique}@example.com",
            password_hash=hash_password("ChangeMe123!"),
        )
        s.add(user)
        await s.flush()

        s.add(Membership(org_id=org.id, user_id=user.id, role="admin"))
        kb = KnowledgeBase(org_id=org.id, name=f"kb-{unique}", visibility="org")
        s.add(kb)
        await s.commit()

        return IntegrationContext(
            org_id=org.id,
            user_id=user.id,
            kb_id=kb.id,
            token=create_access_token(str(user.id)),
        )


def _cleanup_context(org_id: uuid.UUID) -> None:
    async def _delete() -> None:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Organization).where(Organization.id == org_id))
            await s.commit()

    _run(_delete())


@pytest.fixture
def temp_storage(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_markdown_upload_ready_duplicate_and_chunks(temp_storage: Path) -> None:
    unique = uuid.uuid4().hex[:12]
    ctx = _run(_create_context(unique))
    try:
        content = (
            "# 门禁管理\n\n"
            "## 适用范围\n\n"
            "总部及分支机构全体员工适用。\n\n"
            "## 通行规则\n\n"
            "员工应刷卡进入办公区。\n"
        ).encode()
        auth = {"Authorization": f"Bearer {ctx.token}"}
        files = {
            "file": (
                "../../evil.md",
                content,
                "text/markdown",
            )
        }

        with TestClient(app) as client:
            resp = client.post(
                f"/knowledge-bases/{ctx.kb_id}/documents",
                files=files,
                headers=auth,
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert body["status"] == "ready", body
            assert body["original_filename"] == "evil.md"
            doc_id = body["id"]

            # 重复上传相同内容：409，且不产生额外有效分块
            resp2 = client.post(
                f"/knowledge-bases/{ctx.kb_id}/documents",
                files=files,
                headers=auth,
            )
            assert resp2.status_code == 409, resp2.text

            chunks = client.get(
                f"/documents/{doc_id}/chunks", headers=auth
            )
            assert chunks.status_code == 200, chunks.text
            chunk_list = chunks.json()
            assert len(chunk_list) >= 2
            for chunk in chunk_list:
                assert chunk["content"].strip()
                assert chunk["chunk_index"] >= 0
                assert chunk["locator"]["char_start"] >= 0
                assert chunk["locator"]["char_end"] > chunk["locator"]["char_start"]
                assert "section_path" in chunk["locator"]
    finally:
        _cleanup_context(ctx.org_id)


def test_damaged_pdf_becomes_failed(temp_storage: Path) -> None:
    unique = uuid.uuid4().hex[:12]
    ctx = _run(_create_context(unique))
    try:
        auth = {"Authorization": f"Bearer {ctx.token}"}
        pdf = Path(__file__).with_name("fixtures") / "broken.pdf"

        with TestClient(app) as client:
            resp = client.post(
                f"/knowledge-bases/{ctx.kb_id}/documents",
                files={"file": ("broken.pdf", pdf.read_bytes(), "application/pdf")},
                headers=auth,
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert body["status"] == "failed"
            assert body["error_message"]
    finally:
        _cleanup_context(ctx.org_id)
