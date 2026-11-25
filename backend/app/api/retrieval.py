import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_access_scope, require_admin
from app.db import get_db
from app.db.models import Membership
from app.services.access import AccessScope
from app.services.retrieval import SearchResult, hybrid_search, keyword_search, vector_search

router = APIRouter(prefix="/debug", tags=["debug"])


class DebugSearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    kb_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=50)


def _serialize(results: list[SearchResult]) -> list[dict]:
    return [
        {
            "chunk_id": str(r.chunk_id),
            "document_id": str(r.document_id),
            "content": r.content,
            "locator": r.locator,
            "vector_rank": r.vector_rank,
            "vector_score": r.vector_score,
            "keyword_rank": r.keyword_rank,
            "keyword_score": r.keyword_score,
            "rrf_score": r.rrf_score,
            "final_rank": r.final_rank,
        }
        for r in results
    ]


@router.post("/search")
async def debug_search(
    payload: DebugSearchRequest,
    admin: Membership = Depends(require_admin),
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """只读调试接口：对比向量、关键词、混合三种检索的完整追踪。"""
    vector_results = await vector_search(db, scope, payload.question, top_k=payload.top_k)
    keyword_results = await keyword_search(db, scope, payload.question, top_k=payload.top_k)
    hybrid_results = await hybrid_search(
        db,
        scope,
        payload.question,
        vector_top_k=payload.top_k,
        keyword_top_k=payload.top_k,
    )
    return {
        "question": payload.question,
        "vector": _serialize(vector_results),
        "keyword": _serialize(keyword_results),
        "hybrid": _serialize(hybrid_results),
    }