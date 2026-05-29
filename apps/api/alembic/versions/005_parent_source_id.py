"""add parent_source_id to knowledge_sources

Revision ID: 005
Revises: 004
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'knowledge_sources',
        sa.Column('parent_source_id', UUID(as_uuid=False), nullable=True)
    )
    op.create_foreign_key(
        'fk_knowledge_sources_parent_source_id',
        'knowledge_sources', 'knowledge_sources',
        ['parent_source_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        'ix_knowledge_sources_parent_source_id',
        'knowledge_sources', ['parent_source_id']
    )


def downgrade() -> None:
    op.drop_index('ix_knowledge_sources_parent_source_id', 'knowledge_sources')
    op.drop_constraint(
        'fk_knowledge_sources_parent_source_id', 'knowledge_sources', type_='foreignkey'
    )
    op.drop_column('knowledge_sources', 'parent_source_id')
