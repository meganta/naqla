"""add teacher profile and methodology to tenant_settings

Revision ID: 007
Revises: 006
Create Date: 2026-05-29
"""
import sqlalchemy as sa

from alembic import op

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Academic profile
    op.add_column('tenant_settings', sa.Column('subject', sa.String(200), nullable=True))
    op.add_column('tenant_settings', sa.Column('grade_level', sa.String(100), nullable=True))
    op.add_column('tenant_settings', sa.Column('curriculum_country', sa.String(100), nullable=True))
    op.add_column('tenant_settings', sa.Column('curriculum_name', sa.String(200), nullable=True))
    op.add_column('tenant_settings', sa.Column('school_name', sa.String(300), nullable=True))
    op.add_column('tenant_settings', sa.Column('academic_year', sa.String(20), nullable=True))
    op.add_column('tenant_settings', sa.Column('teaching_language', sa.String(50), nullable=True))
    op.add_column('tenant_settings', sa.Column('student_level', sa.String(50), nullable=True))
    # Copilot behavior
    op.add_column('tenant_settings', sa.Column('copilot_tone', sa.String(50), nullable=True))
    op.add_column(
        'tenant_settings', sa.Column('copilot_response_language', sa.String(50), nullable=True)
    )
    # Methodology
    op.add_column(
        'tenant_settings', sa.Column('methodology_template', sa.String(100), nullable=True)
    )
    op.add_column('tenant_settings', sa.Column('teaching_style', sa.String(100), nullable=True))
    op.add_column('tenant_settings', sa.Column('explanation_depth', sa.String(50), nullable=True))


def downgrade() -> None:
    for col in [
        'subject', 'grade_level', 'curriculum_country', 'curriculum_name',
        'school_name', 'academic_year', 'teaching_language', 'student_level',
        'copilot_tone', 'copilot_response_language',
        'methodology_template', 'teaching_style', 'explanation_depth',
    ]:
        op.drop_column('tenant_settings', col)
