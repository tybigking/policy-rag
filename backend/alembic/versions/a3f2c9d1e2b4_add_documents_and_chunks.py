"""add documents and chunks

Revision ID: a3f2c9d1e2b4
Revises: 65fa47341a23
Create Date: 2026-11-14 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3f2c9d1e2b4'
down_revision: Union[str, Sequence[str], None] = '65fa47341a23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'documents',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('kb_id', sa.Uuid(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_key', sa.String(length=500), nullable=False),
        sa.Column('file_format', sa.String(length=20), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column(
            'status',
            sa.String(length=20),
            server_default=sa.text("'uploaded'"),
            nullable=False,
        ),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("file_format IN ('pdf', 'markdown')", name='ck_documents_file_format'),
        sa.CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name='ck_documents_status',
        ),
        sa.CheckConstraint('size_bytes >= 0', name='ck_documents_size_bytes'),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kb_id', 'content_hash', name='uq_documents_kb_content_hash'),
    )
    op.create_index('ix_documents_kb_id', 'documents', ['kb_id'], unique=False)
    op.create_index('ix_documents_kb_status', 'documents', ['kb_id', 'status'], unique=False)
    op.create_index('ix_documents_org_id', 'documents', ['org_id'], unique=False)

    op.create_table(
        'chunks',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('kb_id', sa.Uuid(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('locator', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('chunk_index >= 0', name='ck_chunks_chunk_index'),
        sa.CheckConstraint('char_length(content) > 0', name='ck_chunks_content_not_empty'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_chunks_document_chunk_index'),
    )
    op.create_index('ix_chunks_kb_id', 'chunks', ['kb_id'], unique=False)
    op.create_index('ix_chunks_org_id', 'chunks', ['org_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_chunks_org_id', table_name='chunks')
    op.drop_index('ix_chunks_kb_id', table_name='chunks')
    op.drop_table('chunks')
    op.drop_index('ix_documents_org_id', table_name='documents')
    op.drop_index('ix_documents_kb_status', table_name='documents')
    op.drop_index('ix_documents_kb_id', table_name='documents')
    op.drop_table('documents')
