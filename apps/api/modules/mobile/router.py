import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai import get_ai_provider
from core.database import get_db
from modules.ingestion.models import KnowledgeChunk, KnowledgeSource
from modules.mobile.evidence_builder import (
    YOUTUBE_TYPES,
    _get_int,
    _get_str,
    build_youtube_playback_url,
)
from modules.mobile.schemas import (
    PlaybackResponse,
    SnapshotQuestionRequest,
    SnapshotQuestionResponse,
)
from modules.mobile.snapshot_service import process_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile", tags=["mobile"])


@router.post(
    "/snapshot-questions",
    response_model=SnapshotQuestionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_snapshot_question(
    payload: SnapshotQuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a snapshot question request from the mobile app.
    Runs OCR (or uses ocr_override for testing), detects questions,
    retrieves tenant knowledge, and returns grounded answers with evidence.
    """
    request_id = f"req_{uuid4().hex[:12]}"
    logger.info(
        "POST /mobile/snapshot-questions request_id=%s tenant=%s",
        request_id, payload.tenant_id,
    )

    if not payload.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant_id is required",
        )

    provider = await get_ai_provider(tenant_id=payload.tenant_id, db=db)

    result = await process_snapshot(
        db=db,
        provider=provider,
        request=payload,
        request_id=request_id,
    )
    return result


@router.get(
    "/evidence/{evidence_id}/playback",
    response_model=PlaybackResponse,
)
async def get_evidence_playback(
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return playback metadata for a given evidence_id.
    evidence_id format: ev_<chunk_uuid>
    TODO: generate signed GCS URL for audio/video sources.
    """
    if not evidence_id.startswith("ev_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid evidence_id format",
        )

    chunk_id = evidence_id[3:]

    result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id)
    )
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    source_result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id == chunk.source_id)
    )
    source = source_result.scalar_one_or_none()
    source_type = (
        chunk.source_type_tag or (source.source_type if source else "")
    ) or "text"

    start_ms = _get_int(chunk, 'start_ms')
    end_ms = _get_int(chunk, 'end_ms')
    youtube_video_id = _get_str(chunk, 'youtube_video_id')

    playback_url = None
    if source_type in YOUTUBE_TYPES and youtube_video_id:
        playback_url = build_youtube_playback_url(youtube_video_id, start_ms)
    # TODO: generate signed GCS URL for audio/video

    return PlaybackResponse(
        evidence_id=evidence_id,
        source_type=source_type,
        playback_url=playback_url,
        start_ms=start_ms,
        end_ms=end_ms,
        youtube_video_id=youtube_video_id,
    )
