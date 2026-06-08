"""backfill start_ms, end_ms, youtube_video_id from extra_meta JSON

Revision ID: 010
Revises: 009
Create Date: 2026-06-08
"""
from alembic import op

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extract youtube_video_id from extra_meta JSON
    op.execute("""
        UPDATE knowledge_chunks
        SET youtube_video_id = extra_meta::json->>'video_id'
        WHERE extra_meta IS NOT NULL
          AND extra_meta::json->>'video_id' IS NOT NULL
          AND youtube_video_id IS NULL
    """)

    # Convert HH:MM:SS start_time -> milliseconds
    op.execute("""
        UPDATE knowledge_chunks
        SET start_ms = (
            SPLIT_PART(extra_meta::json->>'start_time', ':', 1)::int * 3600000 +
            SPLIT_PART(extra_meta::json->>'start_time', ':', 2)::int * 60000 +
            SPLIT_PART(extra_meta::json->>'start_time', ':', 3)::int * 1000
        )
        WHERE extra_meta IS NOT NULL
          AND extra_meta::json->>'start_time' IS NOT NULL
          AND start_ms IS NULL
    """)

    # Convert HH:MM:SS end_time -> milliseconds
    op.execute("""
        UPDATE knowledge_chunks
        SET end_ms = (
            SPLIT_PART(extra_meta::json->>'end_time', ':', 1)::int * 3600000 +
            SPLIT_PART(extra_meta::json->>'end_time', ':', 2)::int * 60000 +
            SPLIT_PART(extra_meta::json->>'end_time', ':', 3)::int * 1000
        )
        WHERE extra_meta IS NOT NULL
          AND extra_meta::json->>'end_time' IS NOT NULL
          AND end_ms IS NULL
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE knowledge_chunks
        SET start_ms = NULL, end_ms = NULL, youtube_video_id = NULL
        WHERE source_type_tag = 'youtube'
    """)
