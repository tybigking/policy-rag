"""阶段 4：检索编排。统一 SearchResult，保留每一路排名供调试追踪。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ChunkEmbedding, DocumentChunk
from app.services.access import AccessScope
from app.services.embedding import embed_texts
from app.services.keyword_search import BM25Index


@dataclass(frozen=True)
class SearchResult:
    """混合检索统一结果。rank 一律从 1 开始。"""

    chunk_id: uuid.UUID
    kb_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    locator: dict
    vector_rank: int | None = None
    vector_score: float | None = None
    keyword_rank: int | None = None
    keyword_score: float | None = None
    rrf_score: float | None = None
    final_rank: int | None = None


async def vector_search(
    db: AsyncSession,
    scope: AccessScope,
    question: str,
    *,
    top_k: int,
) -> list[SearchResult]:
    """纯向量 Top K：只依赖问题文本，结果按余弦相似度降序。"""
    settings = get_settings()
    vectors = await embed_texts([question])
    query_vector = vectors[0]

    # 余弦距离越小越相似。投影 similarity = 1 - distance，便于人类阅读与排序。
    distance = ChunkEmbedding.embedding.cosine_distance(query_vector)
    similarity = (1.0 - distance).label("score")
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.kb_id,
            DocumentChunk.document_id,
            DocumentChunk.content,
            DocumentChunk.locator,
            similarity,
        )
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .where(
            DocumentChunk.kb_id.in_(scope.readable_kb_ids),
            ChunkEmbedding.model == settings.embedding_model,
            ChunkEmbedding.dim == settings.embedding_dim,
        )
        .order_by(distance.asc())
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()

    results: list[SearchResult] = []
    for rank, row in enumerate(rows, start=1):
        results.append(
            SearchResult(
                chunk_id=row.id,
                kb_id=row.kb_id,
                document_id=row.document_id,
                content=row.content,
                locator=row.locator,
                vector_rank=rank,
                vector_score=round(float(row.score), 6),
            )
        )
    return results


async def keyword_search(
    db: AsyncSession,
    scope: AccessScope,
    question: str,
    *,
    top_k: int,
) -> list[SearchResult]:
    """纯关键词 BM25：在授权范围内对 chunk 正文打分。"""
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.kb_id,
            DocumentChunk.document_id,
            DocumentChunk.content,
            DocumentChunk.locator,
        )
        .where(DocumentChunk.kb_id.in_(scope.readable_kb_ids))
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    docs = [(row.id, row.content) for row in rows]
    index = BM25Index(docs)
    hits = index.score(question, top_k=top_k)
    by_id = {row.id: row for row in rows}

    results: list[SearchResult] = []
    for rank, hit in enumerate(hits, start=1):
        row = by_id[hit.chunk_id]
        results.append(
            SearchResult(
                chunk_id=row.id,
                kb_id=row.kb_id,
                document_id=row.document_id,
                content=row.content,
                locator=row.locator,
                keyword_rank=rank,
                keyword_score=round(hit.score, 6),
            )
        )
    return results


def rrf_fuse(
    result_lists: list[list[SearchResult]], *, k: int = 60
) -> list[SearchResult]:
    """RRF 融合：score = sum(1 / (k + rank))。rank 从 1 开始。"""
    fused: dict[uuid.UUID, SearchResult] = {}
    for results in result_lists:
        for result in results:
            fused.setdefault(result.chunk_id, [])

    per_chunk: dict[uuid.UUID, SearchResult] = {}
    for results in result_lists:
        for result in results:
            existing = per_chunk.get(result.chunk_id)
            if existing is None:
                per_chunk[result.chunk_id] = result
            else:
                per_chunk[result.chunk_id] = _merge_trace(existing, result)

    ranked: list[SearchResult] = []
    for result in per_chunk.values():
        rrf = 0.0
        if result.vector_rank is not None:
            rrf += 1.0 / (k + result.vector_rank)
        if result.keyword_rank is not None:
            rrf += 1.0 / (k + result.keyword_rank)
        ranked.append(
            SearchResult(
                chunk_id=result.chunk_id,
                kb_id=result.kb_id,
                document_id=result.document_id,
                content=result.content,
                locator=result.locator,
                vector_rank=result.vector_rank,
                vector_score=result.vector_score,
                keyword_rank=result.keyword_rank,
                keyword_score=result.keyword_score,
                rrf_score=round(rrf, 6),
            )
        )

    ranked.sort(key=lambda r: r.rrf_score or 0, reverse=True)
    final: list[SearchResult] = []
    for rank, result in enumerate(ranked, start=1):
        final.append(
            SearchResult(
                chunk_id=result.chunk_id,
                kb_id=result.kb_id,
                document_id=result.document_id,
                content=result.content,
                locator=result.locator,
                vector_rank=result.vector_rank,
                vector_score=result.vector_score,
                keyword_rank=result.keyword_rank,
                keyword_score=result.keyword_score,
                rrf_score=result.rrf_score,
                final_rank=rank,
            )
        )
    return final


def _merge_trace(a: SearchResult, b: SearchResult) -> SearchResult:
    return SearchResult(
        chunk_id=a.chunk_id,
        kb_id=a.kb_id,
        document_id=a.document_id,
        content=a.content,
        locator=a.locator,
        vector_rank=a.vector_rank if a.vector_rank is not None else b.vector_rank,
        vector_score=a.vector_score if a.vector_score is not None else b.vector_score,
        keyword_rank=a.keyword_rank if a.keyword_rank is not None else b.keyword_rank,
        keyword_score=a.keyword_score if a.keyword_score is not None else b.keyword_score,
    )


async def hybrid_search(
    db: AsyncSession,
    scope: AccessScope,
    question: str,
    *,
    vector_top_k: int | None = None,
    keyword_top_k: int | None = None,
) -> list[SearchResult]:
    settings = get_settings()
    vector_top_k = vector_top_k or settings.vector_top_k
    keyword_top_k = keyword_top_k or settings.keyword_top_k
    vector_results = await vector_search(db, scope, question, top_k=vector_top_k)
    keyword_results = await keyword_search(db, scope, question, top_k=keyword_top_k)
    return rrf_fuse([vector_results, keyword_results], k=settings.rrf_k)