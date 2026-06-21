"""create teacher_style_profiles table

Revision ID: 013
Revises: 012
Create Date: 2026-06-21
"""
import sqlalchemy as sa

from alembic import op

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'teacher_style_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('profile_json', sa.Text(), nullable=False),
        sa.Column('chunks_analyzed', sa.Integer(), default=0),
        sa.Column('sources_analyzed', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        'ix_teacher_style_profiles_tenant_id',
        'teacher_style_profiles',
        ['tenant_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_teacher_style_profiles_tenant_id', 'teacher_style_profiles')
    op.drop_table('teacher_style_profiles')
