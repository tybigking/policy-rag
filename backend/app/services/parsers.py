"""文档解析与分块。

设计要点：
- Markdown：先按标题层级切出章节边界，再在章节内部做定长字符窗口切块，
  保证任何分块都不会跨章节；locator 记录 section_path 和全文字符区间。
- PDF：逐页提取文本，空白页跳过不切块；分块在单页内完成，locator 记录
  page_number 和页内字符区间。扫描版 PDF（无文本层）明确报错，OCR 不在第一版范围。
"""

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader


class ParseError(Exception):
    """文档无法解析或没有可检索文本。"""


@dataclass(frozen=True)
class SectionBlock:
    """Markdown 的一个章节。start/end 是规范化后全文的字符区间。"""

    section_path: list[str]
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ChunkDraft:
    """尚未入库的分块草稿，locator 是可直接反查原文的结构。"""

    content: str
    locator: dict


def normalize_text(text: str) -> str:
    """统一换行并去掉 NUL 等控制字符，不破坏可检索正文。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)


def _heading_of(line: str) -> tuple[int, str] | None:
    """识别 ATX 标题，返回 (层级, 标题文本)；非标题返回 None。"""
    match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
    if not match:
        return None
    level = len(match.group(1))
    title = match.group(2).strip().rstrip("#").strip()
    if not title:
        return None
    return level, title


def parse_markdown(text: str) -> tuple[str, list[SectionBlock]]:
    """解析 Markdown 标题层级。返回 (规范化全文, 章节列表)。"""
    normalized = normalize_text(text)
    sections: list[SectionBlock] = []
    heading_stack: list[str] = []
    current: SectionBlock | None = None

    pos = 0
    for line in normalized.splitlines(keepends=True):
        line_end = pos + len(line)
        cleaned = line.rstrip("\n")
        heading = _heading_of(cleaned)

        if heading is not None:
            if current is not None:
                sections.append(current)
            level, title = heading
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            # 当前章节起始位置就是标题行本身的位置
            current = SectionBlock(
                section_path=list(heading_stack),
                start=pos,
                end=line_end,
                text=line,
            )
        else:
            if current is None:
                # 出现在第一个标题之前的正文（可选序言），section_path 为空
                current = SectionBlock(section_path=[], start=pos, end=line_end, text=line)
            else:
                current = SectionBlock(
                    section_path=current.section_path,
                    start=current.start,
                    end=line_end,
                    text=current.text + line,
                )

        pos = line_end

    if current is not None:
        sections.append(current)
    return normalized, sections


def _chunk_windows(length: int, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """按定长滑动窗口切分。step = chunk_size - overlap。"""
    if length <= 0:
        return []
    step = max(chunk_size - overlap, 1)
    starts = range(0, length, step)
    windows = []
    for start in starts:
        end = min(start + chunk_size, length)
        windows.append((start, end))
        if end == length:
            break
    return windows


def _chunk_section(
    text: str,
    *,
    base_offset: int,
    chunk_size: int,
    overlap: int,
    page_number: int | None = None,
    section_path: list[str] | None = None,
) -> list[ChunkDraft]:
    """章节内的纯文本切块；base_offset 是 text 在规范化全文中的起点。"""
    core = text.strip()
    if not core:
        return []
    lead = len(text) - len(text.lstrip())
    base = base_offset + lead
    chunks: list[ChunkDraft] = []

    for start, end in _chunk_windows(len(core), chunk_size, overlap):
        content = core[start:end].strip()
        if not content:
            continue
        chunks.append(
            ChunkDraft(
                content=content,
                locator={
                    "page_number": page_number,
                    "section_path": list(section_path or []),
                    "char_start": base + start,
                    "char_end": base + end,
                },
            )
        )
    return chunks


def _has_searchable_body(section_text: str) -> bool:
    """只有标题、没有正文的章节不产生分块，避免无意义的小分块。"""
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _heading_of(stripped) is None:
            return True
    return False


def chunk_markdown(text: str, *, chunk_size: int = 800, overlap: int = 80) -> list[ChunkDraft]:
    """章节优先地切分 Markdown，返回带 locator 的分块草稿。"""
    _, sections = parse_markdown(text)
    chunks: list[ChunkDraft] = []
    for section in sections:
        if not _has_searchable_body(section.text):
            continue
        chunks.extend(
            _chunk_section(
                section.text,
                base_offset=section.start,
                chunk_size=chunk_size,
                overlap=overlap,
                section_path=section.section_path,
            )
        )
    return chunks


def extract_pdf_pages(data: bytes) -> list[str]:
    """逐页提取 PDF 文本。扫描件/损坏文件抛出 ParseError。"""
    if not data.startswith(b"%PDF"):
        raise ParseError("不是有效的 PDF 文件：缺少 PDF 文件头")

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pypdf 抛出的异常类型较分散
        raise ParseError(f"PDF 解析失败：{exc}") from exc

    if getattr(reader, "is_encrypted", False):
        raise ParseError("PDF 已加密，当前版本不支持加密文档")

    try:
        page_list = list(reader.pages)
    except Exception as exc:
        raise ParseError(f"PDF 页面读取失败：{exc}") from exc

    if not page_list:
        raise ParseError("PDF 没有任何页面")

    pages: list[str] = []
    for page in page_list:
        try:
            text = page.extract_text()
        except Exception:  # noqa: BLE001
            text = ""
        pages.append(text or "")

    if all(not page.strip() for page in pages):
        raise ParseError(
            "PDF 未提取到可检索文本：可能为空白文档或扫描件，OCR 不在第一版范围"
        )
    return pages


def chunk_pdf_pages(
    pages: list[str], *, chunk_size: int = 800, overlap: int = 80
) -> list[ChunkDraft]:
    """逐页切分 PDF。空白页自然跳过；locator 的 char_start/end 为页内偏移。"""
    chunks: list[ChunkDraft] = []
    for page_number, page in enumerate(pages, start=1):
        chunks.extend(
            _chunk_section(
                page,
                base_offset=0,
                chunk_size=chunk_size,
                overlap=overlap,
                page_number=page_number,
            )
        )
    return chunks


