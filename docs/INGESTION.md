# 文档摄取（阶段 2）

## 支持的范围

| 格式 | 支持方式 | 定位信息 |
| --- | --- | --- |
| Markdown（.md / .markdown） | 按 ATX 标题层级（`#` 到 `######`）切分章节 | `section_path` + 规范化全文的 `char_start` / `char_end` |
| PDF（.pdf） | pypdf 逐页提取文本 | `page_number` + 页内 `char_start` / `char_end` |

## 明确限制

- 只支持原生文本 PDF。扫描版 PDF（没有文本层）会解析失败并标记 `failed`，错误信息说明 OCR 不在第一版范围。
- 加密 PDF 会失败。
- Markdown 必须是 UTF-8；GBK 等编码会解析失败。
- 第一版不做文档版本管理和增量重传；同一知识库内内容哈希相同的文件会被拒绝重复上传。
- 单文件大小上限默认 20 MB（`MAX_UPLOAD_SIZE_BYTES`）。
- 解析是同步的：上传请求返回时，文档已进入 `ready` 或 `failed`。

## 处理状态

| 状态 | 含义 |
| --- | --- |
| `uploaded` | 文件已落盘，尚未开始解析 |
| `processing` | 正在解析和切块 |
| `ready` | 解析成功，chunks 已全部写入 |
| `failed` | 解析失败，`error_message` 保存可理解错误，不会伪装成功 |

## 文件与路径安全

- 原始文件名只作为元数据保存在 `documents.original_filename`。
- 磁盘路径只由 `kb_id`（UUID）和 `uuid4().hex + 后缀` 组成，例如 `storage/<kb_id>/<32位随机名>.pdf`。
- 用户提供的文件名不会参与任何路径拼接，因此 `../`、绝对路径等均无法把文件写到存储目录之外。
- 存储根目录由 `STORAGE_DIR` 配置；相对路径始终基于 `backend/` 解释。

## 分块与定位原理

大模型上下文窗口有限，全文直接塞入不仅浪费 token，也让检索粒度变粗。我们按“章节优先 + 定长窗口”切块：

1. Markdown 先解析标题层级，把文章切成互不重叠的章节（section），再在每个章节内部按 `CHUNK_SIZE`（默认 800 字符）、`CHUNK_OVERLAP`（默认 80 字符）滑动窗口切块。这样任意一个分块都不会横跨两个章节。
2. PDF 不做虚假的“章节”推断，逐页提取文本，在单页内定长滑动切块；空白页直接跳过。

每个 chunk 的 `locator` 是一个 JSONB 对象：

```json
{
  "page_number": 2,
  "section_path": ["员工手册", "第二章 考勤"],
  "char_start": 120,
  "char_end": 920
}
```

- `page_number` 解决“点击引用打开 PDF 第几页”。
- `section_path` 解决“Markdown 中位于哪个章节”。
- `char_start` / `char_end` 解决“原文中从哪个字符到哪个字符”，用于将来高亮片段。
- PDF 的字符区间是**页内偏移**；Markdown 的字符区间是**规范化全文偏移**。

## 幂等与去重

- `documents` 表有 `UNIQUE(kb_id, content_hash)`，重复上传不会生成第二条有效文档。
- `chunks` 表有 `UNIQUE(document_id, chunk_index)`，重复切块不会生成重复分块。
- 一次解析失败会回滚本次已插入的 chunks，再把文档置为 `failed`，不会留下半个成功状态。

## 失败处理

- 空文件：HTTP 422，不落盘、不入库。
- 不支持的扩展名：HTTP 422，不落盘、不入库。
- 损坏 PDF / 无文本 PDF / 非 UTF-8 Markdown：文档记录保留为 `failed`，`error_message` 可见，方便排查。

## 验证方式

```powershell
cd backend

# 单元测试
.\.venv\Scripts\python.exe -m pytest

# 上传接口集成测试（需要本机 PostgreSQL）
.\.venv\Scripts\python.exe -m pytest -m integration
```
