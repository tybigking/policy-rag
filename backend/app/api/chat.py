import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_access_scope
from app.core.security import get_current_user
from app.db import get_db
from app.db.models import Citation, Conversation, Document, DocumentChunk, Message, User
from app.services.access import AccessScope
from app.services.answer import AnswerError, ask_question

router = APIRouter(tags=["chat"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="提问内容")
    kb_ids: list[uuid.UUID] | None = Field(
        default=None, description="限定检索的知识库；为空表示搜索全部授权知识库"
    )
    conversation_id: uuid.UUID | None = Field(default=None, description="追加到已有会话")


class CitationOut(BaseModel):
    id: uuid.UUID | None = None
    label: str
    chunk_id: uuid.UUID
    locator: dict
    content: str


class AskResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    status: str
    mode: str
    model: str | None
    error_message: str | None
    citations: list[CitationOut]
    latency_ms: int


class ConversationOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    preview: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    status: str
    error_message: str | None
    model: str | None
    mode: str | None
    latency_ms: int | None
    created_at: datetime
    citations: list[CitationOut] = []


class CitationDetail(BaseModel):
    id: uuid.UUID
    label: str
    chunk_id: uuid.UUID
    content: str
    locator: dict
    document: dict


@router.post("/chat/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    user: User = Depends(get_current_user),
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> AskResponse:
    try:
        result = await ask_question(
            db,
            user,
            scope,
            question=payload.question,
            kb_ids=payload.kb_ids,
            conversation_id=payload.conversation_id,
        )
    except AnswerError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return AskResponse(
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        answer=result.answer,
        status=result.status,
        mode=result.mode,
        model=result.model,
        error_message=result.error_message,
        citations=[
            CitationOut(id=c.id, label=c.label, chunk_id=c.chunk_id, locator=c.locator,
                        content=c.content)
            for c in result.citations
        ],
        latency_ms=result.latency_ms,
    )


@router.get("/chat/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user),
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationOut]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.org_id == scope.org_id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
    )
    conversations = list(result.scalars().all())

    out: list[ConversationOut] = []
    for conversation in conversations:
        last = (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        preview = last.content[:60] if last else ""
        out.append(ConversationOut(id=conversation.id, created_at=conversation.created_at,
                                   preview=preview))
    return out


@router.get("/chat/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id or conversation.org_id != scope.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    messages = list(
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
        ).scalars().all()
    )

    citation_result = await db.execute(
        select(Citation).where(Citation.message_id.in_([m.id for m in messages]))
    )
    citations_by_message: dict[uuid.UUID, list[Citation]] = {}
    for citation in citation_result.scalars().all():
        citations_by_message.setdefault(citation.message_id, []).append(citation)

    out: list[MessageOut] = []
    for message in messages:
        out.append(
            MessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                status=message.status,
                error_message=message.error_message,
                model=message.model,
                mode=message.mode,
                latency_ms=message.latency_ms,
                created_at=message.created_at,
                citations=[
                    CitationOut(id=c.id, label=c.label, chunk_id=c.chunk_id,
                                locator=c.locator_snapshot, content=c.content_snapshot)
                    for c in sorted(citations_by_message.get(message.id, []), key=lambda c: c.label)
                ],
            )
        )
    return out


@router.get("/citations/{citation_id}", response_model=CitationDetail)
async def get_citation(
    citation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    scope: AccessScope = Depends(get_access_scope),
    db: AsyncSession = Depends(get_db),
) -> CitationDetail:
    """读取引用原文：删除授权后，旧引用不能再展示原文。"""
    citation = await db.get(Citation, citation_id)
    if citation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="引用不存在")

    message = await db.get(Message, citation.message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="引用不存在")
    conversation = await db.get(Conversation, message.conversation_id)
    if conversation is None or conversation.user_id != user.id or conversation.org_id != scope.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="引用不存在")

    chunk = await db.get(DocumentChunk, citation.chunk_id)
    if chunk is None or not scope.can_read(chunk.kb_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="引用不存在或无权访问")

    document = await db.get(Document, chunk.document_id)
    return CitationDetail(
        id=citation.id,
        label=citation.label,
        chunk_id=citation.chunk_id,
        content=chunk.content,
        locator=chunk.locator,
        document={
            "id": document.id if document else None,
            "name": document.original_filename if document else "已删除文档",
        },
    )