"""delete gibberish English-only chunks from audio/video/youtube sources

These are bad Whisper transcriptions of Arabic speech that produced garbled English text.
They have no Arabic characters and contain sequences of 4+ English letters.
Deleting them improves copilot retrieval accuracy.

Revision ID: 012
Revises: 011
Create Date: 2026-06-10
"""
from alembic import op

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete chunks that are English-only (no Arabic chars) from transcription sources
    # Also nullify their embeddings first to free pgvector index space
    op.execute("""
        DELETE FROM knowledge_chunks
        WHERE source_type_tag IN ('youtube', 'video', 'audio')
        AND content_text ~ '[a-zA-Z]{4,}'
        AND content_text !~ '[\u0600-\u06FF]'
    """)


def downgrade() -> None:
    # Cannot restore deleted chunks
    pass
