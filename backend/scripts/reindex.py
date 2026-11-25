"""索引回填：为所有 ready 分块生成当前模型的向量。

幂等：同一 chunk 在当前 model 下已有一条向量时跳过；重复执行不产生重复记录。
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db.models import ChunkEmbedding, DocumentChunk
from app.services.embedding import EmbeddingError, embed_texts


async def main(limit: int | None = None, chunk_id: str | None = None) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    written = 0
    skipped = 0
    try:
        async with Session() as s:
            stmt = select(DocumentChunk).order_by(DocumentChunk.created_at)
            if chunk_id:
                stmt = stmt.where(DocumentChunk.id == chunk_id)
            if limit:
                stmt = stmt.limit(limit)

            rows = list((await s.execute(stmt)).scalars().all())
            # 维度一致性检查：同模型存在不同维度时明确报错，拒绝继续写入
            mismatched = await s.execute(
                select(ChunkEmbedding).where(
                    ChunkEmbedding.model == settings.embedding_model,
                    ChunkEmbedding.dim != settings.embedding_dim,
                ).limit(1)
            )
            if mismatched.scalars().first() is not None:
                raise SystemExit(
                    f"维度不一致：已存在模型 {settings.embedding_model} 的其他维度向量，"
                    "请先清理或更换模型后重建"
                )

            for row in rows:
                existing = (
                    await s.execute(
                        select(ChunkEmbedding).where(
                            ChunkEmbedding.chunk_id == row.id,
                            ChunkEmbedding.model == settings.embedding_model,
                        )
                    )
                ).scalars().first()
                if existing is not None:
                    skipped += 1
                    continue

                vectors = await embed_texts([row.content])
                s.add(
                    ChunkEmbedding(
                        chunk_id=row.id,
                        model=settings.embedding_model,
                        dim=settings.embedding_dim,
                        embedding=vectors[0],
                    )
                )
                written += 1

                if written % settings.embedding_batch_size == 0:
                    await s.commit()
            await s.commit()
    finally:
        await engine.dispose()

    print(
        f"reindex done: written={written} skipped={skipped} "
        f"model={settings.embedding_model} dim={settings.embedding_dim}"
    )
    return written


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except EmbeddingError as exc:
        print(f"reindex failed: {exc}")
        sys.exit(1)