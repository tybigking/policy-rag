import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_access_scope, require_admin
from app.config import get_settings
from app.db import get_db
from app.db.models import Document, DocumentChunk, KnowledgeBase, Membership
from app.services.access import AccessScope
from app.services.ingestion import process_document
from app.services.storage import (
    UploadValidationError,
    content_hash,
    delete_stored_file,
    store_upload,
)

router = APIRouter(tags=["documents"])


class DocumentOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    org_id: uuid.UUID
    original_filename: str
    file_format: str
    size_bytes: int
    content_hash: str
    status: str
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    kb_id: uuid.UUID
    org_id: uuid.UUID
    chunk_index: int
    content: str
    locator: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _require_kb_read(scope: AccessScope, kb_id: uuid.UUID) -> None:
    if not scope.can_read(kb_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )


async def _get_kb_for_org(
    db: AsyncSession, kb_id: uuid.UUID, org_id: uuid.UUID
) -> KnowledgeBase:
    kb = (
        await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.org_id == org_id,
            )
        )
    ).scalars().first()
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )
    return kb


async def _get_document_for_scope(
    db: AsyncSession, document_id: uuid.UUID, scope: AccessScope
) -> Document:
    document = (
        await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.org_id == scope.org_id,
            )
        )
    ).scalars().first()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )
    _require_kb_read(scope, document.kb_id)
    return document


@router.get(
    "/knowledge-bases/{kb_id}/documents",
    response_model=list[DocumentOut],
)
async def list_documents(
    kb_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    _require_kb_read(scope, kb_id)
    result = await db.execute(
        select(Document)
        .where(Document.kb_id == kb_id, Document.org_id == scope.org_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/knowledge-bases/{kb_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile = File(...),
    admin: Membership = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Document:
    settings = get_settings()
    kb = await _get_kb_for_org(db, kb_id, admin.org_id)

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="文件为空，不能上传",
        )

    digest = content_hash(data)
    duplicate = (
        await db.execute(
            select(Document).where(
                Document.kb_id == kb.id,
                Document.content_hash == digest,
            )
        )
    ).scalars().first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"文件内容已存在：{duplicate.original_filename}（状态 {duplicate.status}）",
        )

    try:
        stored = store_upload(
            kb_id=kb.id,
            original_filename=file.filename,
            data=data,
            max_upload_size_bytes=settings.max_upload_size_bytes,
        )
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    document = Document(
        org_id=admin.org_id,
        kb_id=kb.id,
        original_filename=stored.original_filename,
        stored_key=stored.storage_key,
        file_format=stored.file_format,
        size_bytes=stored.size_bytes,
        content_hash=stored.content_hash,
        status="uploaded",
    )
    db.add(document)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        delete_stored_file(stored.storage_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="文件内容已存在，请勿重复上传",
        )
    await db.refresh(document)

    await process_document(
        db,
        document,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    await db.refresh(document)
    return document


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> Document:
    return await _get_document_for_scope(db, document_id, scope)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkOut])
async def list_document_chunks(
    document_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentChunk]:
    await _get_document_for_scope(db, document_id, scope)
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())