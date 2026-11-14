"""调试命令：查看某文档的全部分块及 locator。

用法：
    .venv\\Scripts\\python.exe -m scripts.show_chunks <document_id>
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Document, DocumentChunk


async def main(document_id: str) -> None:
    engine = create_async_engine(get_settings().database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        document = (
            await s.execute(select(Document).where(Document.id == document_id))
        ).scalars().first()
        if document is None:
            print("document not found:", document_id)
            return

        print(f"document {document.id}")
        print(f"  original_filename = {document.original_filename}")
        print(f"  file_format       = {document.file_format}")
        print(f"  status            = {document.status}")
        print(f"  page_count        = {document.page_count}")
        if document.error_message:
            print(f"  error_message     = {document.error_message}")

        chunks = (
            await s.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_index)
            )
        ).scalars().all()

        print(f"  chunks            = {len(chunks)}")
        for chunk in chunks:
            print("-" * 60)
            print(f"[{chunk.chunk_index}] {chunk.locator}")
            print(chunk.content)

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(sys.argv[1]))
