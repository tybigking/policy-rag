# PolicyRAG

面向企业内部制度文档的权限感知问答系统。

## 第一版目标

支持管理员上传 PDF 和 Markdown 制度文档，普通员工在自己的知识库权限范围内提问。系统从授权资料中检索证据，返回带页码和章节定位的答案；没有可靠依据时明确拒答。

## 第一版范围

- 管理员和普通员工两种角色
- 知识库创建与用户授权
- PDF 和 Markdown 文档上传
- 文档解析、章节分块和页码定位
- 中文 Embedding 与 pgvector 向量检索
- BM25 或 PostgreSQL 全文检索
- 混合检索和结果追踪
- 权限在检索之前生效
- 回答来源编号和引用校验
- 无依据问题拒答
- 40 题固定评测集
- Docker Compose 本地启动

## 暂不实现

- Agent 工具调用
- Text-to-SQL
- 企业数据库和 SaaS 连接器
- 多种大模型供应商
- 复杂度量角色、计费与 Webhook
- 大规模并发和分布式索引
- 扫描版 PDF 的 OCR

## 主流程

```text
管理员上传文档
  -> 系统解析并生成分块
  -> 分块生成向量和关键词索引
  -> 员工在授权知识库中提问
  -> 系统完成混合检索
  -> 回答模块生成带引用的答案
  -> 界面展示来源和原文位置
```

## 参考来源

项目架构参考 CSV-AI v3 的公开设计思路：

- 参考仓库：https://github.com/Safiullah-Rahu/knowledge-intelligence
- 参考 Commit：`2ea622e159cc5b8733c7621b83ed3b2e1376cadd`
- 本仓库不复用原仓库的 Git 历史。
- 本仓库的应用代码默认独立实现；如后续复制具体代码，将保留原许可证并补充归属说明。

## 当前状态

阶段 2：文档上传解析与可定位分块，已完成并通过验收。

## 后端启动

前提：已安装 Python 3.12，并已启动 PostgreSQL（或用仓库根目录 Docker Compose 启动）。

```powershell
# 1. 创建虚拟环境并安装依赖
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 2. 准备本地环境变量（.env 不提交 Git）
Copy-Item .env.example .env

# 3. 从仓库根目录启动 PostgreSQL + pgvector
cd ..
docker compose up -d

# 4. 回到 backend 执行迁移和种子数据
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed

# 5. 启动 API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --loop app.loop:selector_event_loop
```

启动后：

- Swagger 文档：http://127.0.0.1:8000/docs
- `POST /auth/register` 注册
- `POST /auth/login` 登录并返回 JWT
- `GET /auth/me` 用 Bearer JWT 获取当前用户
- `POST /knowledge-bases` 管理员创建知识库
- `GET /knowledge-bases` 列出当前组织知识库
- `POST /knowledge-bases/{kb_id}/documents` 上传文档（multipart）
- `GET /knowledge-bases/{kb_id}/documents` 列出知识库文档
- `GET /documents/{document_id}` 查看文档状态
- `GET /documents/{document_id}/chunks` 查看全部分块及 locator
- `GET /health` 健康检查

种子账号（仅本地开发）：

- 管理员：`admin@example.com` / `ChangeMe123!`
- 普通员工：`staff@example.com` / `ChangeMe123!`

上传示例：

```powershell
# 先登录拿 token
$token = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"admin@example.com","password":"ChangeMe123!"}').access_token

# 创建知识库
$kb = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/knowledge-bases `
  -Headers @{Authorization="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"name":"员工手册","visibility":"org"}'

# 上传 Markdown/PDF；文件字段名必须是 file
curl.exe -X POST "http://127.0.0.1:8000/knowledge-bases/$($kb.id)/documents" `
  -H "Authorization: Bearer $token" `
  -F "file=@D:\repos\docs\manual.md;type=text/markdown"
```

## 测试

```powershell
cd backend

# 单元测试：解析器、分块、存储安全、auth（不要求数据库）
.\.venv\Scripts\python.exe -m pytest

# 集成测试：真实 PostgreSQL + 临时存储目录的上传链路
.\.venv\Scripts\python.exe -m pytest -m integration
```

覆盖：成功登录、错误密码 401、缺少令牌 401、参数错误 422、Markdown 章节分块、PDF 逐页解析、空白页跳过、损坏 PDF 失败、路径穿越防护、上传接口 ready/failed、重复上传 409。

## 阶段 1 验收（删卷 -> 迁移 -> 种子 -> 登录）

```powershell
# 从仓库根目录删除数据库卷并重启数据库
docker compose down -v
docker compose up -d

cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --loop app.loop:selector_event_loop

# 另开终端登录验证
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"admin@example.com","password":"ChangeMe123!"}'
```

## 阶段 2 验收（上传 -> ready/failed -> 反查 chunks -> 重复上传 409）

说明与限制见 `docs/INGESTION.md`。

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest -m integration

# 调试命令：查看某文档全部分块
.\.venv\Scripts\python.exe -m scripts.show_chunks <document_id>
```
