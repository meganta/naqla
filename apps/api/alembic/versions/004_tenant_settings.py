"""tenant settings table

Revision ID: 004
Revises: 003
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_settings',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=False), nullable=False, unique=True),
        sa.Column('youtube_channel_url', sa.String(1000), nullable=True),
        sa.Column('youtube_channel_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_tenant_settings_tenant_id', 'tenant_settings', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_tenant_settings_tenant_id', 'tenant_settings')
    op.drop_table('tenant_settings')
