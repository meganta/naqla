"""backfill page_number from extra_meta JSON for PDF/DOCX/PPTX chunks

Revision ID: 011
Revises: 010
Create Date: 2026-06-10
"""
from alembic import op

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill page_number from extra_meta for document chunks
    op.execute("""
        UPDATE knowledge_chunks
        SET page_number = (extra_meta::json->>'page_number')::int
        WHERE extra_meta IS NOT NULL
          AND extra_meta::json->>'page_number' IS NOT NULL
          AND page_number IS NULL
          AND source_type_tag IN ('pdf', 'docx', 'pptx')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE knowledge_chunks
        SET page_number = NULL
        WHERE source_type_tag IN ('pdf', 'docx', 'pptx')
    """)
