from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

FILE_SOURCE_TYPES = {"pdf", "docx", "pptx", "audio", "video"}
URL_SOURCE_TYPES = {"youtube", "youtube_channel"}
TEXT_SOURCE_TYPES = {"text", "manual"}
UNSUPPORTED_SOURCE_TYPES = {"facebook", "instagram", "tiktok", "generic_url"}
ALL_SOURCE_TYPES = (
    FILE_SOURCE_TYPES | URL_SOURCE_TYPES | TEXT_SOURCE_TYPES | UNSUPPORTED_SOURCE_TYPES
)

SOURCE_STATUSES = {
    "draft", "upload_pending", "uploaded", "processing",
    "processed", "failed", "unsupported", "partially_processed",
}
JOB_STATUSES = {
    "pending", "processing", "completed", "failed",
    "unsupported", "partially_completed",
}


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    teacher_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    parent_source_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("knowledge_sources.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    jobs: Mapped[list["IngestionJob"]] = relationship("IngestionJob", back_populates="source")
    child_sources: Mapped[list["KnowledgeSource"]] = relationship(
        "KnowledgeSource", foreign_keys="KnowledgeSource.parent_source_id",
        back_populates="parent_source",
    )
    parent_source: Mapped["KnowledgeSource | None"] = relationship(
        "KnowledgeSource", foreign_keys="KnowledgeSource.parent_source_id",
        back_populates="child_sources", remote_side="KnowledgeSource.id",
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("knowledge_sources.id"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source: Mapped["KnowledgeSource"] = relationship(
        "KnowledgeSource", back_populates="jobs"
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("knowledge_sources.id"), nullable=False
    )
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grade_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extra_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), nullable=False, unique=True
    )
    youtube_channel_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    youtube_channel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Academic profile
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    curriculum_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    curriculum_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    school_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    teaching_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    student_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Copilot behavior
    copilot_tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    copilot_response_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Methodology
    methodology_template: Mapped[str | None] = mapped_column(String(100), nullable=True)
    teaching_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    explanation_depth: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
