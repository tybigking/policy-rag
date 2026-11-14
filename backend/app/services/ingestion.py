"""文档摄取编排：uploaded -> processing -> ready/failed。

状态机刻意保持简单：解析成功才允许写入 chunks；任何解析错误都会把文档
标记为 failed 并保存可理解错误，绝不伪装成功。
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentChunk
from app.services.parsers import (
    ChunkDraft,
    ParseError,
    chunk_markdown,
    chunk_pdf_pages,
    extract_pdf_pages,
)
from app.services.storage import read_stored_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedDocument:
    file_format: str
    page_count: int | None
    chunks: list[ChunkDraft]


def parse_uploaded_file(data: bytes, file_format: str, *, chunk_size: int, chunk_overlap: int) -> ParsedDocument:
    """把落盘文件解析成分块草稿；解析失败向上抛 ParseError。"""
    if file_format == "markdown":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError("Markdown 文件不是有效的 UTF-8 文本") from exc
        chunks = chunk_markdown(text, chunk_size=chunk_size, overlap=chunk_overlap)
        if not chunks:
            raise ParseError("Markdown 文件没有可切分的正文")
        return ParsedDocument(file_format="markdown", page_count=None, chunks=chunks)

    if file_format == "pdf":
        pages = extract_pdf_pages(data)
        chunks = chunk_pdf_pages(pages, chunk_size=chunk_size, overlap=chunk_overlap)
        return ParsedDocument(file_format="pdf", page_count=len(pages), chunks=chunks)

    raise ParseError(f"不支持的文件格式：{file_format}")


async def process_document(
    db: AsyncSession,
    document: Document,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    """执行单个文档的解析与分块入库，并把状态推进到 ready 或 failed。"""
    document.status = "processing"
    await db.commit()

    try:
        data = read_stored_file(document.stored_key)
        parsed = parse_uploaded_file(
            data,
            document.file_format,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        chunk_rows = [
            DocumentChunk(
                document_id=document.id,
                org_id=document.org_id,
                kb_id=document.kb_id,
                chunk_index=index,
                content=chunk.content,
                locator=chunk.locator,
            )
            for index, chunk in enumerate(parsed.chunks)
        ]
        db.add_all(chunk_rows)

        document.status = "ready"
        document.page_count = parsed.page_count
        document.error_message = None
        await db.commit()
        logger.info(
            "document ready id=%s chunks=%d format=%s",
            document.id,
            len(chunk_rows),
            document.file_format,
        )
    except (ParseError, OSError) as exc:
        await db.rollback()
        document.status = "failed"
        document.error_message = str(exc)
        document.page_count = None
        await db.commit()
        logger.warning("document failed id=%s reason=%s", document.id, str(exc))
    except Exception:
        await db.rollback()
        document.status = "failed"
        document.error_message = "内部处理失败，请查看服务端日志"
        document.page_count = None
        await db.commit()
        logger.exception("document internal failure id=%s", document.id)
