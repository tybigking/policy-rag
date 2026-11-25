"""add chunk_embeddings

Revision ID: b7c3a9e1f5d2
Revises: a3f2c9d1e2b4
Create Date: 2026-11-25 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c3a9e1f5d2"
down_revision: str | Sequence[str] | None = "a3f2c9d1e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 必须与 app.config.Settings.embedding_dim 保持一致。更换维度需要新建迁移。
EMBEDDING_DIM = 384


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("dim > 0", name="ck_chunk_embeddings_dim"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", "model", name="uq_chunk_embeddings_chunk_model"),
    )
    op.create_index("ix_chunk_embeddings_chunk_id", "chunk_embeddings", ["chunk_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chunk_embeddings_chunk_id", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")