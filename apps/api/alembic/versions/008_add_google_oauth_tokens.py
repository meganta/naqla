"""add google oauth tokens to tenant_settings
Revision ID: 008
Revises: 007
Create Date: 2026-05-30
"""
import sqlalchemy as sa
from alembic import op
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column('tenant_settings', sa.Column('google_access_token', sa.Text(), nullable=True))
    op.add_column('tenant_settings', sa.Column('google_refresh_token', sa.Text(), nullable=True))
    op.add_column(
        'tenant_settings',
        sa.Column('google_token_expiry', sa.DateTime(), nullable=True)
    )
def downgrade() -> None:
    op.drop_column('tenant_settings', 'google_token_expiry')
    op.drop_column('tenant_settings', 'google_refresh_token')
    op.drop_column('tenant_settings', 'google_access_token')
