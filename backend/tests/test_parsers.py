from pathlib import Path

import pytest

from app.services.parsers import (
    ParseError,
    chunk_markdown,
    chunk_pdf_pages,
    extract_pdf_pages,
    parse_markdown,
)


def test_normal_markdown_chunks_nonempty_and_located(tmp_path: Path) -> None:
    text = (
        "# 请假制度\n\n"
        "## 适用范围\n\n"
        "全体员工适用。\n\n"
        "## 年假\n\n"
        "员工每年享有五天年假。\n"
    )
    chunks = chunk_markdown(text, chunk_size=10000, overlap=0)
    assert len(chunks) == 2

    for chunk in chunks:
        assert chunk.content.strip()
        assert set(chunk.locator) == {"page_number", "section_path", "char_start", "char_end"}
        assert chunk.locator["page_number"] is None
        assert chunk.locator["section_path"]

    assert chunks[0].locator["section_path"] == ["请假制度", "适用范围"]
    assert "全体员工适用" in chunks[0].content
    assert chunks[1].locator["section_path"] == ["请假制度", "年假"]


def test_multilevel_markdown_chapters_do_not_mix(tmp_path: Path) -> None:
    text = (
        "# 员工手册\n\n"
        "## 第一章 入职\n\n"
        "### 1.1 入职材料\n\n"
        "新员工应当提交身份证复印件。\n\n"
        "### 1.2 劳动合同\n\n"
        "劳动合同应在入职当日签订。\n\n"
        "## 第二章 考勤\n\n"
        "### 2.1 工作时间\n\n"
        "工作时间为上午九点到下午六点。\n\n"
        "### 2.2 加班\n\n"
        "加班需要提前申请。\n"
    )
    chunks = chunk_markdown(text, chunk_size=10000, overlap=0)

    paths = [chunk.locator["section_path"] for chunk in chunks]
    assert ["员工手册", "第一章 入职", "1.1 入职材料"] in paths
    assert ["员工手册", "第二章 考勤", "2.2 加班"] in paths

    # 章节优先：不会出现第一章和第二章内容混在同一分块
    for chunk in chunks:
        if "入职材料" in chunk.content:
            assert "工作时间" not in chunk.content
        if "工作时间" in chunk.content:
            assert "入职材料" not in chunk.content


def test_markdown_char_offsets_point_to_full_text(tmp_path: Path) -> None:
    text = (
        "# 员工手册\n\n"
        "## 考勤\n\n"
        "工作时间为上午九点到下午六点。\n"
    )
    normalized, _ = parse_markdown(text)
    chunks = chunk_markdown(text, chunk_size=200, overlap=0)

    target = next(c for c in chunks if "工作时间" in c.content)
    start = target.locator["char_start"]
    end = target.locator["char_end"]
    assert 0 <= start < end <= len(normalized)
    assert "工作时间" in normalized[start:end]


def test_pdf_single_page_extracts_text_and_page_number() -> None:
    pdf = Path(__file__).with_name("fixtures") / "short.pdf"
    pages = extract_pdf_pages(pdf.read_bytes())
    assert len(pages) == 1
    assert "Short Page" in pages[0]

    chunks = chunk_pdf_pages(pages, chunk_size=10000, overlap=0)
    assert len(chunks) == 1
    assert chunks[0].locator["page_number"] == 1
    assert "PolicyRAG" in chunks[0].content


def test_pdf_multi_page_blank_page_is_skipped_in_chunks() -> None:
    pdf = Path(__file__).with_name("fixtures") / "multi_page.pdf"
    pages = extract_pdf_pages(pdf.read_bytes())
    assert len(pages) == 2
    assert pages[1].strip() == ""

    chunks = chunk_pdf_pages(pages, chunk_size=10000, overlap=0)
    assert chunks
    assert all(chunk.locator["page_number"] == 1 for chunk in chunks)


def test_broken_pdf_raises_parse_error() -> None:
    pdf = Path(__file__).with_name("fixtures") / "broken.pdf"
    with pytest.raises(ParseError):
        extract_pdf_pages(pdf.read_bytes())
