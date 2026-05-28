from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.ingestion.models import (
    FILE_SOURCE_TYPES,
    TEXT_SOURCE_TYPES,
    UNSUPPORTED_SOURCE_TYPES,
    URL_SOURCE_TYPES,
)
from modules.ingestion.schemas import (
    CreateSourceRequest,
    JobResponse,
    SourceResponse,
    UploadURLResponse,
)
from modules.ingestion.service import (
    confirm_upload,
    create_source,
    enqueue_ingestion_job,
    generate_signed_upload_url,
    get_job,
    get_latest_job,
    get_source,
    list_sources,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/sources", response_model=UploadURLResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_source(
    payload: CreateSourceRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await create_source(
            db,
            tenant_id=current_user.tenant_id,
            teacher_id=current_user.id,
            title=payload.title,
            source_type=payload.source_type,
            original_url=payload.original_url,
            raw_text=payload.raw_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if payload.source_type in UNSUPPORTED_SOURCE_TYPES:
        return UploadURLResponse(source_id=source.id, upload_url="", file_path="")

    if payload.source_type in URL_SOURCE_TYPES | TEXT_SOURCE_TYPES:
        return UploadURLResponse(source_id=source.id, upload_url="", file_path="")

    upload_url, file_path = generate_signed_upload_url(
        source.id, payload.source_type, current_user.tenant_id
    )
    source.file_path = file_path
    await db.flush()
    return UploadURLResponse(
        source_id=source.id, upload_url=upload_url, file_path=file_path
    )


@router.post("/sources/{source_id}/confirm-upload")
async def confirm_upload_done(
    source_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await confirm_upload(db, source_id, current_user.tenant_id)
        return {"source_id": source.id, "status": source.status}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/sources", response_model=list[SourceResponse])
async def get_sources(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_sources(db, current_user.tenant_id)


@router.post("/sources/{source_id}/process", response_model=JobResponse)
async def process_source(
    source_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await get_source(db, source_id, current_user.tenant_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )
    if source.source_type in UNSUPPORTED_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Source type '{source.source_type}' is not yet supported. "
                "This type is reserved for future integration."
            ),
        )
    if source.source_type in FILE_SOURCE_TYPES and source.status not in {
        "uploaded", "processed", "failed"
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "File must be uploaded before processing. "
                "Call POST /ingestion/sources/{id}/confirm-upload first."
            ),
        )
    job = await enqueue_ingestion_job(db, source_id, current_user.tenant_id)
    return job


@router.get("/sources/{source_id}/job", response_model=JobResponse)
async def get_source_latest_job(
    source_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_latest_job(db, source_id, current_user.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No job found for this source"
        )
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_job(db, job_id, current_user.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return job
