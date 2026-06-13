import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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


class ImageUploadUrlRequest(BaseModel):
    tenant_id: str


class ImageUploadUrlResponse(BaseModel):
    upload_url: str
    image_ref: str


@router.post("/image-upload-url", response_model=ImageUploadUrlResponse)
async def get_image_upload_url(payload: ImageUploadUrlRequest):
    """
    Return a signed GCS PUT URL for the mobile app to upload a snapshot image.
    """
    if not payload.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant_id is required",
        )
    try:
        # Lazy imports to avoid startup failures if GCS libs not installed
        from datetime import timedelta

        import google.auth
        import google.auth.transport.requests
        from google.auth import impersonated_credentials
        from google.cloud import storage

        from core.config import settings

        file_id = uuid4().hex
        file_path = f"snapshots/{payload.tenant_id}/{file_id}.jpg"

        credentials, _ = google.auth.default()
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)

        service_account_email = (
            f"naqla-api-sa@{settings.gcp_project_id}.iam.gserviceaccount.com"
        )
        signing_credentials = impersonated_credentials.Credentials(
            source_credentials=credentials,
            target_principal=service_account_email,
            target_scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
            lifetime=300,
        )
        client = storage.Client(credentials=signing_credentials)
        bucket = client.bucket(settings.gcs_bucket_name)
        blob = bucket.blob(file_path)
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type="image/jpeg",
            credentials=signing_credentials,
        )
        return ImageUploadUrlResponse(
            upload_url=upload_url,
            image_ref=f"gs://{settings.gcs_bucket_name}/{file_path}",
        )
    except Exception as e:
        logger.error("get_image_upload_url failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="تعذّر إنشاء رابط الرفع. يرجى المحاولة مجدداً.",
        ) from e


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found"
        )

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

    return PlaybackResponse(
        evidence_id=evidence_id,
        source_type=source_type,
        playback_url=playback_url,
        start_ms=start_ms,
        end_ms=end_ms,
        youtube_video_id=youtube_video_id,
    )


class TenantInfo(BaseModel):
    tenant_id: str
    name: str
    slug: str


@router.get("/tenants", response_model=list[TenantInfo])
async def list_tenants(db: AsyncSession = Depends(get_db)):
    """Return all available tenants for student access screen."""
    from modules.auth.models import Tenant
    result = await db.execute(
        select(Tenant).order_by(Tenant.name)
    )
    tenants = result.scalars().all()
    return [
        TenantInfo(tenant_id=str(t.id), name=t.name, slug=t.slug)
        for t in tenants
    ]
