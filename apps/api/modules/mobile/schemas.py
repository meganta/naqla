from typing import Literal

from pydantic import BaseModel, Field

# ---------- Request ----------

class SnapshotQuestionRequest(BaseModel):
    tenant_id: str
    student_id: str | None = None
    image_url: str | None = None
    image_ref: str | None = None
    ocr_override: str | None = None
    language: str = "ar"
    answer_mode: Literal["tenant_knowledge_only"] = "tenant_knowledge_only"


# ---------- Evidence ----------

class EvidenceBase(BaseModel):
    evidence_id: str
    source_id: str
    source_title: str
    excerpt: str


class YoutubeEvidence(EvidenceBase):
    source_type: Literal["youtube"] = "youtube"
    youtube_video_id: str
    start_ms: int | None = None
    end_ms: int | None = None
    playback_url: str


class MediaEvidence(EvidenceBase):
    source_type: Literal["audio", "video"]
    start_ms: int | None = None
    end_ms: int | None = None
    playback_url: str | None = None


class DocumentEvidence(EvidenceBase):
    source_type: Literal["pdf", "docx", "pptx"]
    page_number: int | None = None


class TextEvidence(EvidenceBase):
    source_type: Literal["text", "manual"]


EvidenceItem = YoutubeEvidence | MediaEvidence | DocumentEvidence | TextEvidence


# ---------- Answer ----------

class DetectedQuestion(BaseModel):
    question_id: str
    question_text: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = []


# ---------- Response ----------

class SnapshotQuestionResponse(BaseModel):
    request_id: str
    detected_questions: list[DetectedQuestion]
    warnings: list[str] = []


# ---------- Playback ----------

class PlaybackResponse(BaseModel):
    evidence_id: str
    source_type: str
    playback_url: str | None
    start_ms: int | None
    end_ms: int | None
    youtube_video_id: str | None = None
