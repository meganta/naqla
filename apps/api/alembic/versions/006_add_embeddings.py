"""add embedding vector to knowledge_chunks

Revision ID: 006
Revises: 005
Create Date: 2026-05-29
"""
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        'knowledge_chunks',
        sa.Column('embedding', Vector(1536), nullable=True)
    )
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_embedding
        ON knowledge_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL
    """)
    op.create_index(
        'ix_knowledge_chunks_source_id',
        'knowledge_chunks',
        ['source_id'],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_embedding', 'knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_source_id', 'knowledge_chunks')
    op.drop_column('knowledge_chunks', 'embedding')
