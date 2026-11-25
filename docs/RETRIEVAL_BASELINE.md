# 检索基线（阶段 3 + 4）

## 模型与索引

| 项目 | 值 |
| --- | --- |
| Embedding 供应商 | OpenAI 兼容 `/embeddings`（`EMBEDDING_PROVIDER=openai`） |
| 默认模型 | `text-embedding-3-small`（`EMBEDDING_MODEL`） |
| 向量维度 | 384（`EMBEDDING_DIM`；pgvector 列固定为 `vector(384)`） |
| 距离函数 | 余弦距离 `<=>`，展示时转成 `1 - distance` 的相似度 |
| 向量索引 | 第一版数据量小，仅主键 + `chunk_id` 索引；规模扩大后补 HNSW |
| 关键词检索 | Python 内存 BM25（jieba 分词），候选池为授权知识库全部 chunk |
| 融合 | RRF，`score = 1 / (k + rank)`，`RRF_K=60` |

离线开发与测试使用 `EMBEDDING_PROVIDER=mock`：对同一文本返回确定性单位向量，
保证回填幂等可验证，但**没有语义效果**；真实语义检索需配置 OpenAI 兼容接口。

## 20 题基线集

文件：`backend/baseline/retrieval_questions.json`

- 10 个关键词明显的问题（年假、加班、门禁、报销、入职、试用期、考勤、离职、保密、报修）
- 5 个语义改写问题（休息日连休、迟到扣钱、出差住宿、携带证件、离职手续）
- 5 个无关问题（天气、求职信、餐厅、Python 排序、世界杯）

## 如何复跑

```powershell
cd backend
# 上传文档、回填索引后执行（默认管理员视角）
.\.venv\Scripts\python.exe -m scripts.baseline_retrieval
# 结果写回 backend/baseline/retrieval_results.json，并打印三种检索 Top5
```

## 结果对比模板

人工按“相关分块是否进入 Top5”标记每个问题的三路结果后填下表：

| 路径 | 命中题数（/20） | 说明 |
| --- | --- | --- |
| 仅向量 | 待实测 | 语义能力依赖真实 Embedding；mock 下不评估 |
| 仅关键词 | 待实测 | 对精确词命中好，语义改写弱 |
| 混合（RRF） | 待实测 | 期望不劣于两个单一路径 |

> 本环境没有可运行的 PostgreSQL 实例，实测数字留待具备数据库的机器生成。
> 每一条结果都可在调试接口 `POST /debug/search` 中看到两路排名与融合排名。