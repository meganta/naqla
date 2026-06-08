"""
Evidence builder.
Maps KnowledgeChunk rows to typed EvidenceItem DTOs.
Media timestamps are read from chunk columns (start_ms, end_ms, youtube_video_id, page_number)
added in migration 009. If those columns don't exist yet (runtime before migration), falls back
to parsing extra_meta JSON.
"""
import json
import logging

from modules.ingestion.models import KnowledgeChunk, KnowledgeSource
from modules.mobile.schemas import (
    DocumentEvidence,
    EvidenceItem,
    MediaEvidence,
    TextEvidence,
    YoutubeEvidence,
)

logger = logging.getLogger(__name__)

YOUTUBE_TYPES = {"youtube", "youtube_channel"}
AUDIO_VIDEO_TYPES = {"audio", "video"}
DOCUMENT_TYPES = {"pdf", "docx", "pptx"}
TEXT_TYPES = {"text", "manual"}


def _get_int(chunk: KnowledgeChunk, field: str) -> int | None:
    """Read an int field, falling back to extra_meta JSON if column is missing."""
    val = getattr(chunk, field, None)
    if val is not None:
        return int(val)
    # Fallback: extra_meta JSON
    try:
        meta = json.loads(chunk.extra_meta or '{}')
        return int(meta[field]) if field in meta else None
    except Exception:
        return None


def _get_str(chunk: KnowledgeChunk, field: str) -> str | None:
    val = getattr(chunk, field, None)
    if val is not None:
        return str(val)
    try:
        meta = json.loads(chunk.extra_meta or '{}')
        return str(meta[field]) if field in meta else None
    except Exception:
        return None


def build_youtube_playback_url(video_id: str, start_ms: int | None) -> str:
    if start_ms is not None:
        start_s = start_ms // 1000
        return f"https://www.youtube.com/watch?v={video_id}&t={start_s}s"
    return f"https://www.youtube.com/watch?v={video_id}"


def chunk_to_evidence(
    chunk: KnowledgeChunk,
    source: KnowledgeSource,
) -> EvidenceItem | None:
    source_type = (chunk.source_type_tag or source.source_type or "").lower()
    excerpt = (chunk.content_text or "")[:300]
    source_title = source.title or "مصدر غير معروف"
    evidence_id = f"ev_{chunk.id}"

    if source_type in YOUTUBE_TYPES:
        video_id = _get_str(chunk, 'youtube_video_id')
        if not video_id:
            # Try to parse from source original_url
            import re
            url = source.original_url or ""
            m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
            video_id = m.group(1) if m else ""
        if not video_id:
            logger.warning("chunk_to_evidence: youtube chunk %s has no video_id", chunk.id)
            return None
        start_ms = _get_int(chunk, 'start_ms')
        end_ms = _get_int(chunk, 'end_ms')
        return YoutubeEvidence(
            evidence_id=evidence_id,
            source_id=chunk.source_id,
            source_title=source_title,
            excerpt=excerpt,
            youtube_video_id=video_id,
            start_ms=start_ms,
            end_ms=end_ms,
            playback_url=build_youtube_playback_url(video_id, start_ms),
        )

    if source_type in AUDIO_VIDEO_TYPES:
        start_ms = _get_int(chunk, 'start_ms')
        end_ms = _get_int(chunk, 'end_ms')
        # TODO: generate signed GCS playback URL if source.file_path is set
        return MediaEvidence(
            evidence_id=evidence_id,
            source_id=chunk.source_id,
            source_title=source_title,
            excerpt=excerpt,
            source_type=source_type,  # type: ignore[arg-type]
            start_ms=start_ms,
            end_ms=end_ms,
            playback_url=None,  # TODO: generate signed URL from source.file_path
        )

    if source_type in DOCUMENT_TYPES:
        page_number = _get_int(chunk, 'page_number')
        return DocumentEvidence(
            evidence_id=evidence_id,
            source_id=chunk.source_id,
            source_title=source_title,
            excerpt=excerpt,
            source_type=source_type,  # type: ignore[arg-type]
            page_number=page_number,
        )

    # Default: text/manual or unknown
    return TextEvidence(
        evidence_id=evidence_id,
        source_id=chunk.source_id,
        source_title=source_title,
        excerpt=excerpt,
        source_type="text",  # type: ignore[arg-type]
    )
