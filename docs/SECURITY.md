# 安全与权限（阶段 5）

## 角色

| 角色 | 允许的动作 |
| --- | --- |
| `admin` | 创建知识库、上传文档、查看全部知识库、授予/收回读取权限、调试检索 |
| `member` | 查看 `org` 可见知识库 + 被显式 read 授权的知识库、提问、查看自己的引用 |

角色保存在 `memberships.role`；知识库显式授权保存在 `kb_permissions`（只支持 `read`）。

## 知识库可见性

| visibility | 可见范围 |
| --- | --- |
| `org` | 组织内所有成员可读 |
| `restricted` | 仅管理员 + `kb_permissions` 中被 read 授权的成员可读 |

## 统一 access_scope

`app/services/access.py::build_access_scope()` 返回当前用户可读 `kb_id` 集合：

- admin：本组织全部知识库；
- member：`org` 可见知识库 ∪ 显式授权知识库。

所有读取入口在查询前应用该集合，而不是“先查再删”：

- `GET /knowledge-bases`
- `GET /knowledge-bases/{id}`
- `GET /knowledge-bases/{id}/documents`
- `GET /documents/{id}`、`GET /documents/{id}/chunks`
- 向量检索、关键词检索、混合检索
- `POST /chat/ask`（手工传入受限 `kb_id` 会被过滤；全无权时 404）
- `GET /citations/{id}`（重新鉴权）

## 接口保护矩阵

| 方法与路径 | admin | member | 未登录 |
| --- | --- | --- | --- |
| `POST /auth/register` | 公开 | 公开 | 公开 |
| `POST /auth/login` | 公开 | 公开 | 公开 |
| `GET /auth/me` | ✅ | ✅ | 401 |
| `GET /knowledge-bases` | 全部 | 仅授权 | 401 |
| `POST /knowledge-bases` | ✅ | 403 | 401 |
| `GET /knowledge-bases/{id}` | ✅ | 授权可读，否则 404 | 401 |
| `PUT/DELETE /knowledge-bases/{id}/permissions` | ✅ | 403 | 401 |
| `POST /knowledge-bases/{id}/documents` | ✅ | 403 | 401 |
| `GET /documents/{id}`, `/documents/{id}/chunks` | ✅ | 授权可读，否则 404 | 401 |
| `POST /chat/ask` | ✅ | 仅授权范围 | 401 |
| `GET /citations/{id}` | ✅ | 仅自己的引用且重新鉴权 | 401 |
| `POST /debug/search` | ✅ | 403 | 401 |

## 越权防护约定

- 对无权资源统一返回 404（不泄露资源是否存在），写操作返回 403。
- 修改请求里的 `kb_id` 不能扩大权限：检索仍以服务端 `access_scope` 为准。
- 删除授权后，旧回答里的引用点开时重新鉴权，不再展示原文。
- 权限测试：`backend/tests/test_permissions_integration.py`（跨用户、跨知识库、直接引用）。

## 种子数据

`scripts.seed` 创建三个知识库：

- `全员须知`（org）：全员可见；
- `报销制度`（restricted）：授权给普通员工；
- `薪酬保密`（restricted）：仅管理员。

普通员工登录后应只能看到前两个，直接请求 `薪酬保密` 返回 404。