"""阶段 4：20 题检索基线。

依次跑向量、关键词、混合三种检索，输出结果对比表并落盘 JSON。
需要先启动 PostgreSQL、迁移、种子、上传文档并回填索引。
"""
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db.models import Membership
from app.services.access import build_access_scope
from app.services.retrieval import (
    hybrid_search,
    keyword_search,
    vector_search,
)


def _hit_ids(results, top: int = 5) -> list[str]:
    return [str(r.chunk_id) for r in results[:top]]


async def run(questions_path: Path, output_path: Path) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    rows_out = []
    try:
        async with Session() as s:
            # 基线使用管理员视角：可读全部知识库，便于发现问题后再做权限过滤
            membership = (
                await s.execute(
                    select(Membership).where(Membership.role == "admin").limit(1)
                )
            ).scalars().first()
            if membership is None:
                raise SystemExit("没有管理员成员，先执行 scripts.seed")
            scope = await build_access_scope(s, membership)

            for item in questions:
                q = item["question"]
                v = await vector_search(s, scope, q, top_k=5)
                k = await keyword_search(s, scope, q, top_k=5)
                h = await hybrid_search(s, scope, q)
                record = {
                    "id": item["id"],
                    "category": item["category"],
                    "question": q,
                    "vector_top5": _hit_ids(v),
                    "keyword_top5": _hit_ids(k),
                    "hybrid_top5": _hit_ids(h),
                }
                rows_out.append(record)
                print(f"[{item['id']}] {q}")
                print(f"  vector : {record['vector_top5']}")
                print(f"  keyword: {record['keyword_top5']}")
                print(f"  hybrid : {record['hybrid_top5']}")
    finally:
        await engine.dispose()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresults written to {output_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    default_questions = BACKEND_ROOT / "baseline" / "retrieval_questions.json"
    default_output = BACKEND_ROOT / "baseline" / "retrieval_results.json"
    questions_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_questions
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else default_output
    asyncio.run(run(questions_path, output_path))