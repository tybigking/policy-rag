import uuid

from app.services.answer import build_context, build_source_map, extractive_answer
from app.services.retrieval import SearchResult


def _result(content: str, *, page=None, section=None) -> SearchResult:
    locator: dict = {"page_number": page, "section_path": section or [], "char_start": 0, "char_end": 1}
    return SearchResult(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        locator=locator,
        final_rank=1,
    )


def test_build_context_numbers_and_locates_sources() -> None:
    results = [
        _result("年假五天。", page=3, section=["员工手册", "年假"]),
        _result("加班需要审批。", page=None, section=["员工手册", "加班"]),
    ]
    source_map = build_source_map(results)
    context = build_context(source_map)
    assert "[S1]" in context
    assert "[S2]" in context
    assert "第3页" in context
    assert "员工手册 / 年假" in context


def test_extractive_answer_cites_real_sources() -> None:
    source_map = build_source_map([_result("员工每年享有五天年假。")])
    answer = extractive_answer("年假几天", source_map)
    assert "[S1]" in answer
    assert "五天年假" in answer