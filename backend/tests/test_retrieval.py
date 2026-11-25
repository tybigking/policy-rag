import uuid

from app.services.retrieval import SearchResult, rrf_fuse


def _result(chunk_id: str, *, vector_rank=None, vector_score=None, keyword_rank=None,
            keyword_score=None):
    return SearchResult(
        chunk_id=uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id),
        kb_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=chunk_id,
        locator={},
        vector_rank=vector_rank,
        vector_score=vector_score,
        keyword_rank=keyword_rank,
        keyword_score=keyword_score,
    )


def test_rrf_fuse_merges_ranks_from_both_paths() -> None:
    a_top_vector = _result("a", vector_rank=1, vector_score=0.9)
    a_low_keyword = _result("a", keyword_rank=5, keyword_score=0.2)
    b_keyword = _result("b", keyword_rank=1, keyword_score=8.0)

    fused = rrf_fuse([[a_top_vector, b_keyword], [b_keyword, a_low_keyword]], k=60)

    assert fused[0].final_rank == 1
    assert fused[0].rrf_score is not None
    # 同时出现在两路的结果，保留两路排名
    by_id = {r.chunk_id: r for r in fused}
    a = by_id[uuid.uuid5(uuid.NAMESPACE_DNS, "a")]
    assert a.vector_rank == 1
    assert a.keyword_rank == 5


def test_rrf_score_reciprocal_rank() -> None:
    single = _result("a", vector_rank=2)
    fused = rrf_fuse([[single]], k=0)
    assert fused[0].rrf_score == 1 / 2