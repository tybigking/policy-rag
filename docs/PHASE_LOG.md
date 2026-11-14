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
