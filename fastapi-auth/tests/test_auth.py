import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    """每个测试用例使用独立的内存数据库，互不影响。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(client, username="alice", password="secret123"):
    return client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )


def test_login_success(client):
    """注册后登录成功，返回 access_token。"""
    assert _register(client).status_code == 201

    resp = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client):
    """密码错误返回 401。"""
    _register(client)

    resp = client.post(
        "/auth/login",
        json={"username": "alice", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_missing_token(client):
    """缺少令牌访问 /auth/me 返回 401。"""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_register_invalid_payload(client):
    """密码过短等参数错误返回 422。"""
    resp = client.post(
        "/auth/register",
        json={"username": "bob", "password": "123"},
    )
    assert resp.status_code == 422
