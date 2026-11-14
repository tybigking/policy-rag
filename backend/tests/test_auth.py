import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db import get_db
from app.db.models import User
from app.main import app


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeDBSession:
    """测试用的极简会话：路由只执行单次查询、添加、提交和刷新。"""

    def __init__(self, result):
        self.result = result
        self.added = []

    async def execute(self, stmt):
        return _FakeResult(self.result)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.created_at is None:
            obj.created_at = datetime.now(UTC)


def _call(result, request_fn):
    """用 FakeDBSession 替换 get_db 后执行一次请求，结束后清理覆盖。"""
    fake = FakeDBSession(result)

    async def override_get_db():
        yield fake

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            return request_fn(client, fake)
    finally:
        app.dependency_overrides.clear()


def _existing_user(password="secret123"):
    return User(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash=hash_password(password),
        created_at=datetime.now(UTC),
    )


def test_login_success():
    """正确密码登录成功，返回 bearer JWT。"""
    def run(client, fake):
        return client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "secret123"},
        )

    resp = _call(_existing_user(), run)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password():
    """错误密码返回 401。"""
    def run(client, fake):
        return client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "wrong-password"},
        )

    resp = _call(_existing_user(), run)
    assert resp.status_code == 401


def test_me_missing_token():
    """缺少令牌访问 /auth/me 返回 401。"""
    def run(client, fake):
        return client.get("/auth/me")

    resp = _call(None, run)
    assert resp.status_code == 401


def test_register_invalid_payload():
    """密码过短等参数错误返回 422。"""
    def run(client, fake):
        return client.post(
            "/auth/register",
            json={"email": "staff@example.com", "password": "123"},
        )

    resp = _call(None, run)
    assert resp.status_code == 422
