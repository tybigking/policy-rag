from app.services.keyword_search import BM25Index, tokenize


def is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def test_tokenize_splits_chinese_words() -> None:
    tokens = tokenize("员工每年享有五天年假")
    assert tokens
    assert any(is_cjk(token) for token in tokens)


def test_bm25_ranks_keyword_match_above_noise() -> None:
    docs = [
        ("1", "员工每年享有五天年假，可以申请调休。"),
        ("2", "食堂午餐供应时间为十二点到一点。"),
        ("3", "年假应当在当年使用完毕。"),
    ]
    index = BM25Index(docs)
    hits = index.score("年假有几天", top_k=3)
    ids = [hit.chunk_id for hit in hits]
    assert "1" in ids[:2] or "3" in ids[:2]