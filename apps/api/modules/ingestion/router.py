from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.ingestion.models import KnowledgeSource
from modules.ingestion.schemas import (
    CreateSourceRequest,
    JobResponse,
    SourceResponse,
    UploadURLResponse,
)
from modules.ingestion.service import (
    ALLOWED_SOURCE_TYPES,
    create_source,
    enqueue_ingestion_job,
    generate_signed_upload_url,
    get_job,
    list_sources,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/sources", response_model=UploadURLResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_source(
    payload: CreateSourceRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type. Allowed: {ALLOWED_SOURCE_TYPES}",
        )
    source = await create_source(
        db,
        tenant_id=current_user.tenant_id,
        teacher_id=current_user.id,
        title=payload.title,
        source_type=payload.source_type,
        original_url=payload.original_url,
    )
    if payload.source_type in {"youtube", "manual"}:
        return UploadURLResponse(source_id=source.id, upload_url="", file_path="")
    upload_url, file_path = generate_signed_upload_url(
        source.id, payload.source_type, current_user.tenant_id
    )
    source.file_path = file_path
    await db.flush()
    return UploadURLResponse(source_id=source.id, upload_url=upload_url, file_path=file_path)


@router.get("/sources", response_model=list[SourceResponse])
async def get_sources(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sources = await list_sources(db, current_user.tenant_id)
    return sources


@router.post("/sources/{source_id}/process", response_model=JobResponse)
async def process_source(
    source_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.tenant_id == current_user.tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    job = await enqueue_ingestion_job(db, source_id, current_user.tenant_id)
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_job(db, job_id, current_user.tenant_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
