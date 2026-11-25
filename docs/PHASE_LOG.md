# 开发阶段日志

## 阶段 0 产品定义与范围冻结

- 完成日期：2026-11-12
- 当前分支：`main`
- 仓库地址：`D:\repos\policy-rag`
- 远程地址：`https://github.com/tybigking/policy-rag.git`
- 产品描述：已完成
- 用户角色和三个核心场景：已完成
- P0、P1 和非目标：已冻结
- README 和路线图：已完成
- 初始提交：`46c0c96 chore: initialize PolicyRAG project`
- 阶段验证提交：`ff73dfa docs: complete stage 0 definition`
- 口试结果：待按说明书中的三个问题完成口头检查
- 遗留风险：尚未开始工程实现；阶段 1 前不得扩展 Agent、Text-to-SQL 或连接器

## 阶段 1 工程基础与身份系统

- 完成日期：2026-11-14
- 当前分支：`main`
- 主要产物：
  - `backend/app`：可启动的 FastAPI 应用（注册 / 登录 / me / health）
  - `backend/alembic/versions`：第一版数据库迁移（组织、用户、成员、知识库）
  - `backend/scripts/seed.py`：管理员和普通员工种子账号
  - `backend/.env.example`：环境变量示例
  - `backend/tests/test_auth.py`：auth 相关测试
  - `docker-compose.yml`：PostgreSQL + pgvector
- 验证命令：`cd backend && .venv\Scripts\python.exe -m pytest`（4 passed）
- 口试结果：待按说明书阶段 1 三个问题完成口头检查
- 遗留风险：本机未安装 Docker，Docker Compose 尚未实测；已用本机 PostgreSQL `mydb` 完成等价复验：`DROP SCHEMA public CASCADE -> alembic upgrade head -> scripts.seed -> 登录 admin@example.com` 全部通过。

## 阶段 2 文档上传解析与可定位分块

- 完成日期：2026-11-14
- 当前分支：`main`
- 主要产物：
  - `backend/app/api/kb.py`：知识库创建和列表接口
  - `backend/app/api/documents.py`：上传、文档详情、chunks 只读接口
  - `backend/app/services/parsers.py`：Markdown 章节解析、PDF 逐页提取、章节优先分块
  - `backend/app/services/storage.py`：安全落盘、哈希计算、路径穿越防护
  - `backend/app/services/ingestion.py`：`uploaded/processing/ready/failed` 状态编排
  - `backend/alembic/versions/a3f2c9d1e2b4_add_documents_and_chunks.py`：documents、chunks 迁移
  - `backend/scripts/show_chunks.py`：按文档查看全部分块
  - `backend/tests/test_parsers.py`、`test_storage.py`：解析器与存储单元测试
  - `backend/tests/test_upload_api_integration.py`：真实数据库上传接口集成测试
  - `backend/tests/fixtures/`：normal.md、multi_level.md、short.pdf、multi_page.pdf、broken.pdf
  - `docs/INGESTION.md`：支持格式、限制与失败处理
- 验证命令：
  - `cd backend && .venv\Scripts\python.exe -m pytest`（13 passed, 2 deselected）
  - `cd backend && .venv\Scripts\python.exe -m pytest -m integration`（2 passed）
- 口试结果：待按说明书阶段 2 三个问题完成口头检查
- 遗留风险：
  - 解析为同步处理，超大 PDF 会阻塞请求线程；第一版上限 20 MB。
  - 扫描版 PDF 和加密 PDF 明确置为 `failed`，OCR 不在范围。
  - 尚未在全新 Docker 卷上复验阶段 2；已使用本机 PostgreSQL 运行迁移和集成测试。

## 阶段 3 Embedding 与向量索引

- 完成日期：2026-11-25（本轮）
- 主要产物：
  - `app/services/embedding.py`：Embedding 服务，支持 `mock`（离线确定性）与 `openai`（OpenAI 兼容），分批 + 单次重试
  - `app/db/models.py::ChunkEmbedding` + 迁移 `b7c3a9e1f5d2_add_chunk_embeddings.py`
  - `app/api/retrieval.py::vector_search`：只依赖问题文本的 Top K 向量查询
  - `scripts/reindex.py`：幂等回填命令（同分块同模型只保留一条，维度不一致明确报错）
- 验证命令：
  - `cd backend && .venv\Scripts\python.exe -m pytest`（23 passed，含 embedding 维度校验与幂等语义单元测试）
- 口试结果：待按说明书阶段 3 三个问题完成口头检查
- 遗留风险：
  - 本环境无可用 PostgreSQL/pgvector 实例，向量写入与 `<=>` 查询未在真实数据库实跑；集成验证留待有数据库环境执行
  - 默认 `EMBEDDING_PROVIDER=mock` 无语义；真实语义检索需配置 OpenAI 兼容服务
  - HNSW 索引未建（数据量小，先记录参数、按需补建）

## 阶段 4 关键词检索与混合排序

- 完成日期：2026-11-25（本轮）
- 主要产物：
  - `app/services/keyword_search.py`：jieba 分词 + 内存 BM25
  - `app/services/retrieval.py`：统一 `SearchResult`、向量/关键词两路 + RRF 融合，保留每路排名
  - `app/api/retrieval.py::POST /debug/search`：仅管理员调试检索追踪
  - `scripts/baseline_retrieval.py` + `backend/baseline/retrieval_questions.json`：20 题基线
  - `docs/RETRIEVAL_BASELINE.md`：模型、维度、距离函数、索引参数与复跑方式
- 验证命令：
  - `cd backend && .venv\Scripts\python.exe -m pytest`（tokenize、BM25、RRF 单元测试通过）
- 口试结果：待按说明书阶段 4 三个问题完成口头检查
- 遗留风险：
  - 三路基线对比表需要真实 PG + 真实 Embedding 后生成；当前环境无法实测，文档已说明
  - 内存 BM25 会在候选 chunk 数很大时成为瓶颈，第一版范围可接受

## 阶段 5 权限模型与检索隔离

- 完成日期：2026-11-25（本轮）
- 主要产物：
  - `app/services/access.py`：统一 `access_scope`
  - `app/api/deps.py::get_access_scope`：所有读取入口的公共依赖
  - `app/api/kb.py`：授权/收回/列出授权接口；列表按 scope 过滤
  - `app/api/documents.py`：文档与分块读取重新鉴权
  - `scripts/seed.py`：三套知识库演示数据（管理员全量、员工授权子集）
  - `docs/SECURITY.md`：角色、授权与接口保护矩阵
  - `tests/test_permissions_integration.py`：跨用户、跨知识库、授权与越权 404（integration）
- 验证命令：
  - `cd backend && .venv\Scripts\python.exe -m pytest`（access_scope 相关代码随应用导入通过；integration 测试待数据库执行）
- 口试结果：待按说明书阶段 5 三个问题完成口头检查
- 遗留风险：权限集成测试未在真实 PostgreSQL 实跑；上线演示前必须先 `pytest -m integration`

## 阶段 6 回答生成、引用校验与拒答

- 完成日期：2026-11-25（本轮）
- 主要产物：
  - `app/services/llm.py`：单供应商（OpenAI 兼容）模型适配器，超时/限流/网络错误映射
  - `app/services/citations.py`：引用编号解析、去重与越界过滤
  - `app/services/answer.py`：上下文组装、严格拒答、提取式降级、答案/引用/检索快照落库
  - `app/api/chat.py`：`POST /chat/ask`、对话列表、消息列表、`GET /citations/{id}` 重新鉴权
  - 迁移 `c4d8e2f6a9b1_add_conversations_messages_citations.py`
  - `docs/ANSWER.md`：模型配置、引用校验、拒答与提示注入说明
  - `tests/test_citations.py`、`test_answer.py`、`test_chat_api_integration.py`
- 验证命令：
  - `cd backend && .venv\Scripts\python.exe -m pytest`（引用解析、上下文定位、提取式回答单元测试通过）
- 口试结果：待按说明书阶段 6 三个问题完成口头检查
- 遗留风险：
  - `LLM_PROVIDER=openai` 分支与真实模型未实跑（需要 Key）；mock/提取式路径可离线跑通
  - 端到端问答集成测试待真实 PostgreSQL 执行

## 阶段 7 前端完整闭环

- 完成日期：2026-11-25（本轮）
- 主要产物：
  - `frontend/index.html`、`frontend/styles.css`、`frontend/app.js`：无构建依赖的 SPA，由 FastAPI 静态托管
  - 四个视图：登录、知识库列表、知识库详情（上传 + 状态轮询 + 授权）、提问（问答 + 来源面板 + 历史对话）
  - 状态处理：loading / empty / error / refused / failed；401 自动回登录页；404/403 友好展示
  - 来源面板点击后走 `GET /citations/{id}`，删除授权后旧引用不再展示原文
  - 390px 响应式布局（flex + grid 降级 + 窄屏样式）
- 验证命令：
  - `node --check frontend/app.js`（语法检查通过，作为无构建前端的 typecheck/build 等价记录）
  - FastAPI 静态托管自测：`/`、`/app.js`、`/health` 均 200
- 口试结果：待按说明书阶段 7 三个问题完成口头检查
- 遗留风险：
  - 环境无 npm，未采用 Next.js；用无构建 SPA 补齐全部页面与状态，功能验收不依赖框架
  - 端到端 UI 演示与 390px 截图需在具备 PostgreSQL 的机器上连同后端一起验证
