# PolicyRAG

面向企业内部制度文档的权限感知问答系统。管理员上传 PDF 和 Markdown 制度文档，
系统完成解析、分块、向量/关键词混合检索和权限过滤；普通员工在授权知识库内提问，
得到带页码/章节定位的答案，没有可靠依据时明确拒答。

## 第一版范围

- 管理员和普通员工两种角色
- 知识库创建、`org`/`restricted` 可见性与 read 授权
- PDF 和 Markdown 文档上传、解析、章节分块和页码定位
- 中文 Embedding 与 pgvector 向量检索
- jieba + BM25 关键词检索与 RRF 混合排序
- 权限在检索之前生效（统一 `access_scope`）
- 回答来源编号、引用校验与严格拒答
- 提取式降级（离线也可演示）
- 无构建前端：登录、知识库、上传、提问、来源面板
- Docker Compose（PostgreSQL + pgvector）

## 暂不实现

- Agent 工具调用、Text-to-SQL
- 多种大模型供应商、扫描版 PDF 的 OCR
- 流式回答、文档版本管理、增量更新
- 大规模并发与分布式索引

## 主流程

```text
管理员上传文档
  -> 解析并生成可定位分块
  -> 回填向量 + 关键词索引
  -> 员工在授权知识库中提问
  -> 混合检索（权限内）
  -> 回答模块生成带引用的答案
  -> 前端展示答案、来源与原文定位
```

## 项目结构

```text
backend/           FastAPI 应用、Alembic 迁移、脚本与测试
frontend/          无构建 SPA（由 FastAPI 静态托管）
docs/              阶段说明、安全、检索基线、回答设计
docker-compose.yml PostgreSQL + pgvector
```

详细设计见：

- `docs/INGESTION.md`：文档摄取与可定位分块
- `docs/RETRIEVAL_BASELINE.md`：模型、维度、索引与 20 题基线
- `docs/SECURITY.md`：角色、授权与接口保护矩阵
- `docs/ANSWER.md`：回答、引用校验、拒答与降级
- `docs/PHASE_LOG.md`：各阶段完成记录

## 后端启动

前提：Python 3.12，已启动 PostgreSQL（或从仓库根目录用 Docker Compose 启动）。

```powershell
# 1. 创建虚拟环境并安装依赖
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]

# 2. 准备本地环境变量（.env 不提交 Git）
Copy-Item .env.example .env

# 3. 从仓库根目录启动 PostgreSQL + pgvector
cd ..
docker compose up -d

# 4. 回到 backend 执行迁移和种子数据
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed

# 5. 启动 API（同时托管前端）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --loop app.loop:selector_event_loop
```

启动后打开：

- 前端：http://127.0.0.1:8000/
- Swagger：http://127.0.0.1:8000/docs

种子账号（仅本地开发）：

- 管理员：`admin@example.com` / `ChangeMe123!`
- 普通员工：`staff@example.com` / `ChangeMe123!`

## 主要 API

| 方法与路径 | 用途 | 权限 |
| --- | --- | --- |
| `POST /auth/register` | 注册 | 公开 |
| `POST /auth/login` | 登录获取 JWT | 公开 |
| `GET /auth/me` | 当前用户与角色 | 已登录 |
| `GET /knowledge-bases` | 列出授权知识库 | 已登录 |
| `POST /knowledge-bases` | 创建知识库 | admin |
| `PATCH/PUT/DELETE /knowledge-bases/{id}/...` | 查看/授权知识库 | 见 `docs/SECURITY.md` |
| `POST /knowledge-bases/{id}/documents` | 上传文档 | admin |
| `GET /documents/{id}`、`/documents/{id}/chunks` | 文档状态与分块 | 授权 read |
| `POST /chat/ask` | 提问返回答案与引用 | 授权 read |
| `GET /chat/conversations`、`.../{id}/messages` | 历史会话 | 本人 |
| `GET /citations/{id}` | 查看引用原文（重新鉴权） | 重新鉴权 |
| `POST /debug/search` | 检索调试追踪 | admin |
| `GET /health` | 健康检查 | 公开 |

## 向量索引回填

上传文档 `ready` 后，执行回填（幂等，重复执行不会产生重复记录）：

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.reindex
```

离线默认 `EMBEDDING_PROVIDER=mock`（确定性向量，无语义，便于验证流程）。
要获得真实语义检索，在 `.env` 配置：

```text
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=384
```

## 回答模型

离线默认 `LLM_PROVIDER=mock`，直接走提取式降级；配置 OpenAI 兼容接口后走模型：

```text
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_MODEL=gpt-4o-mini
```

完整环境变量见 `backend/.env.example`。

## 测试

```powershell
cd backend

# 单元测试（解析、存储、embedding、BM25、RRF、引用、auth；不要求数据库）
.\.venv\Scripts\python.exe -m pytest

# 集成测试（需要本机 PostgreSQL，覆盖上传、权限、问答链路）
.\.venv\Scripts\python.exe -m pytest -m integration
```

前端语法检查（无构建前端）：

```powershell
node --check frontend/app.js
```

## 检索基线

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.baseline_retrieval
```

结果写入 `backend/baseline/retrieval_results.json`，详见 `docs/RETRIEVAL_BASELINE.md`。

## 参考来源

项目架构参考 CSV-AI v3 的公开设计思路：

- 参考仓库：https://github.com/Safiullah-Rahu/knowledge-intelligence
- 参考 Commit：`2ea622e159cc5b8733c7621b83ed3b2e1376cadd`
- 本仓库不复用原仓库的 Git 历史。
- 本仓库的应用代码默认独立实现；如后续复制具体代码，将保留原许可证并补充归属说明。