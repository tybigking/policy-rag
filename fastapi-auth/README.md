# FastAPI Auth API

一个最小可运行的 FastAPI 认证项目：注册、登录（签发 JWT）、获取当前用户，
密码用 Argon2 哈希，数据库用 SQLite + SQLAlchemy + Alembic 迁移。

## 功能

- `POST /auth/register` 注册
- `POST /auth/login` 登录并返回 JWT
- `GET /auth/me` 用 Bearer JWT 获取当前用户
- `GET /health` 健康检查

## 项目结构

```
app/
  main.py            # FastAPI 入口
  config.py          # 读取 .env 配置
  db.py              # SQLAlchemy 引擎、会话、get_db 依赖
  models.py          # User ORM 模型
  api/auth.py        # 注册/登录/me 路由
  core/security.py   # Argon2 + JWT + get_current_user
  seed.py            # 演示用户种子脚本
alembic/             # 数据库迁移
tests/test_auth.py   # pytest 测试
```

## 本地启动

```powershell
cd D:\repos\policy-rag\fastapi-auth
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 配置环境变量（开发可直接用仓库内的 .env）
Copy-Item .env.example .env

# 初始化数据库：迁移 + 种子用户
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed

# 启动服务
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

浏览器打开：<http://127.0.0.1:8000/docs>

演示用户：`alice / secret123`

## 完整复验流程（删卷 -> 迁移 -> 种子 -> 登录）

```powershell
# 1. 删掉旧数据库
.\.venv\Scripts\python.exe -c "import os; os.path.exists('auth.db') and os.remove('auth.db')"

# 2. 迁移建表
.\.venv\Scripts\python.exe -m alembic upgrade head

# 3. 写入演示用户
.\.venv\Scripts\python.exe -m app.seed

# 4. 启动并登录
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login `
  -ContentType "application/json" -Body '{"username":"alice","password":"secret123"}'
```

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

覆盖场景：成功登录、错误密码 401、缺令牌 401、参数错误 422。

