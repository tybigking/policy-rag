"""add conversations messages citations

Revision ID: c4d8e2f6a9b1
Revises: b7c3a9e1f5d2
Create Date: 2026-11-25 00:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8e2f6a9b1"
down_revision: str | Sequence[str] | None = "b7c3a9e1f5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_org_user",
        "conversations",
        ["org_id", "user_id"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'submitted'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retrieval_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        sa.CheckConstraint(
            "status IN ('submitted', 'answered', 'refused', 'failed')",
            name="ck_messages_status",
        ),
        sa.CheckConstraint(
            "mode IS NULL OR mode IN ('llm', 'extractive')", name="ck_messages_mode"
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)

    op.create_table(
        "citations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=10), nullable=False),
        sa.Column("locator_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "label", name="uq_citations_message_label"),
    )
    op.create_index("ix_citations_message_id", "citations", ["message_id"], unique=False)
    op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_citations_chunk_id", table_name="citations")
    op.drop_index("ix_citations_message_id", table_name="citations")
    op.drop_table("citations")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_org_user", table_name="conversations")
    op.drop_table("conversations")