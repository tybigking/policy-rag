import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,                      # 应用层生成
        server_default=text("gen_random_uuid()"), # 数据库层兜底
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Membership(Base):
    __tablename__ = "memberships"

    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_memberships_role"),
        Index("ix_memberships_user_id", "user_id"),
    )


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="org",
        server_default=text("'org'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_knowledge_bases_org_name"),
        CheckConstraint(
            "visibility IN ('org', 'restricted')", name="ck_knowledge_bases_visibility"
        ),
        Index("ix_knowledge_bases_org_id", "org_id"),
    )


class KnowledgeBasePermission(Base):
    """知识库显式授权：只支持 read 级别。"""

    __tablename__ = "kb_permissions"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    access_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="read", server_default=text("'read'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("access_level IN ('read')", name="ck_kb_permissions_access_level"),
        Index("ix_kb_permissions_user_id", "user_id"),
    )


class Document(Base):
    """知识库内的原始文档。文件落盘名与原始文件名分离，避免路径穿越。"""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploaded", server_default=text("'uploaded'")
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("kb_id", "content_hash", name="uq_documents_kb_content_hash"),
        CheckConstraint(
            "file_format IN ('pdf', 'markdown')", name="ck_documents_file_format"
        ),
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name="ck_documents_status",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_documents_size_bytes"),
        Index("ix_documents_org_id", "org_id"),
        Index("ix_documents_kb_id", "kb_id"),
        Index("ix_documents_kb_status", "kb_id", "status"),
    )


class DocumentChunk(Base):
    """可检索分块。locator 保存页码、章节路径和字符区间，用于反查原文。"""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_chunk_index"),
        CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index"),
        CheckConstraint("char_length(content) > 0", name="ck_chunks_content_not_empty"),
        Index("ix_chunks_org_id", "org_id"),
        Index("ix_chunks_kb_id", "kb_id"),
    )


class ChunkEmbedding(Base):
    """分块向量。同一分块同一模型只保留一条；dim 与模型名一起留档。"""

    __tablename__ = "chunk_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("chunk_id", "model", name="uq_chunk_embeddings_chunk_model"),
        CheckConstraint("dim > 0", name="ck_chunk_embeddings_dim"),
        Index("ix_chunk_embeddings_chunk_id", "chunk_id"),
    )


class Conversation(Base):
    """一次问答会话。第一版每次提问可新建会话，也支持追加到已有会话。"""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_conversations_org_user", "org_id", "user_id"),
    )


class Message(Base):
    """会话内的问题与答案。retrieval_snapshot 保存检索快照便于排查。"""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="submitted", server_default=text("'submitted'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        CheckConstraint(
            "status IN ('submitted', 'answered', 'refused', 'failed')",
            name="ck_messages_status",
        ),
        CheckConstraint(
            "mode IS NULL OR mode IN ('llm', 'extractive')", name="ck_messages_mode"
        ),
        Index("ix_messages_conversation_id", "conversation_id"),
    )


class Citation(Base):
    """答案引用：保存回答时的 chunk 快照，查看时仍要重新鉴权。"""

    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(10), nullable=False)
    locator_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("message_id", "label", name="uq_citations_message_label"),
        Index("ix_citations_message_id", "message_id"),
        Index("ix_citations_chunk_id", "chunk_id"),
    )