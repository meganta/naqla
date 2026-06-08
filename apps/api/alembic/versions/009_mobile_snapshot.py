"""add mobile snapshot support: media fields on chunks + snapshot_requests table

Revision ID: 009
Revises: 008
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add media timestamp fields to knowledge_chunks
    op.add_column('knowledge_chunks', sa.Column('start_ms', sa.Integer(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('end_ms', sa.Integer(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('youtube_video_id', sa.String(50), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('page_number', sa.Integer(), nullable=True))

    # Snapshot requests table for traceability
    op.create_table(
        'snapshot_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('student_id', sa.String(255), nullable=True),
        sa.Column('image_ref', sa.Text(), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('language', sa.String(10), default='ar'),
        sa.Column('answer_mode', sa.String(50), default='tenant_knowledge_only'),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        'ix_snapshot_requests_tenant_id',
        'snapshot_requests',
        ['tenant_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_snapshot_requests_tenant_id', 'snapshot_requests')
    op.drop_table('snapshot_requests')
    for col in ['start_ms', 'end_ms', 'youtube_video_id', 'page_number']:
        op.drop_column('knowledge_chunks', col)
