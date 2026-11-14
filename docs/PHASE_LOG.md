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

- 完成日期：2026-11-14（代码与测试就绪；Docker 实机复验待本机安装 Docker 后执行）
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
- 遗留风险：本机未安装 Docker，`删卷 -> 迁移 -> 种子 -> 登录` 的完整复验尚未在本地执行；待 Docker 就绪后补验。