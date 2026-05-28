# ruff: noqa: I001
"""ingestion tables

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:01.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("teacher_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("original_url", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_knowledge_sources_tenant_id", "knowledge_sources", ["tenant_id"])
    op.create_index("ix_knowledge_sources_teacher_id", "knowledge_sources", ["teacher_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "source_id",
            UUID(as_uuid=False),
            sa.ForeignKey("knowledge_sources.id"),
            nullable=False,
        ),
        sa.Column("tenant_id", UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunks_created", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])
    op.create_index("ix_ingestion_jobs_tenant_id", "ingestion_jobs", ["tenant_id"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "source_id",
            UUID(as_uuid=False),
            sa.ForeignKey("knowledge_sources.id"),
            nullable=False,
        ),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("source_type_tag", sa.String(50), nullable=True),
        sa.Column("subject_tag", sa.String(100), nullable=True),
        sa.Column("grade_tag", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_tenant_id", "knowledge_chunks", ["tenant_id"])
    op.create_index("ix_knowledge_chunks_source_id", "knowledge_chunks", ["source_id"])


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("ingestion_jobs")
    op.drop_table("knowledge_sources")
