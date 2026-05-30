import json
from datetime import datetime, timedelta

import google.auth
import google.auth.transport.requests
from google.auth import impersonated_credentials
from google.cloud import storage, tasks_v2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.ingestion.models import (
    FILE_SOURCE_TYPES,
    UNSUPPORTED_SOURCE_TYPES,
    IngestionJob,
    KnowledgeChunk,
    KnowledgeSource,
)


def generate_signed_upload_url(
    source_id: str, source_type: str, tenant_id: str
) -> tuple[str, str]:
    extension_map = {
        "pdf": "pdf", "docx": "docx", "pptx": "pptx",
        "audio": "mp3", "video": "mp4",
    }
    ext = extension_map.get(source_type, "bin")
    file_path = f"uploads/{tenant_id}/{source_id}.{ext}"

    credentials, _project = google.auth.default()
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
        credentials=signing_credentials,
    )
    return upload_url, file_path


async def create_source(
    db: AsyncSession,
    tenant_id: str,
    teacher_id: str,
    title: str,
    source_type: str,
    original_url: str | None = None,
    raw_text: str | None = None,
) -> KnowledgeSource:
    from modules.ingestion.models import ALL_SOURCE_TYPES

    if source_type not in ALL_SOURCE_TYPES:
        raise ValueError(
            f"Unknown source type: {source_type}. "
            f"Allowed: {sorted(ALL_SOURCE_TYPES)}"
        )

    if source_type in UNSUPPORTED_SOURCE_TYPES:
        initial_status = "unsupported"
    elif source_type in FILE_SOURCE_TYPES:
        initial_status = "upload_pending"
    else:
        initial_status = "draft"

    source = KnowledgeSource(
        tenant_id=tenant_id,
        teacher_id=teacher_id,
        title=title,
        source_type=source_type,
        original_url=original_url,
        raw_text=raw_text,
        status=initial_status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(source)
    await db.flush()
    return source


async def confirm_upload(
    db: AsyncSession, source_id: str, tenant_id: str
) -> KnowledgeSource:
    result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.tenant_id == tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise ValueError("Source not found")

    source.status = "uploaded"
    source.updated_at = datetime.utcnow()
    await db.flush()
    return source


async def list_sources(db: AsyncSession, tenant_id: str) -> list:
    """List sources with latest job error_message attached."""
    from sqlalchemy import and_, func

    latest_job_subq = (
        select(
            IngestionJob.source_id,
            func.max(IngestionJob.created_at).label("max_created_at"),
        )
        .where(IngestionJob.tenant_id == tenant_id)
        .group_by(IngestionJob.source_id)
        .subquery()
    )
    latest_job_error = (
        select(IngestionJob.source_id, IngestionJob.error_message)
        .join(
            latest_job_subq,
            and_(
                IngestionJob.source_id == latest_job_subq.c.source_id,
                IngestionJob.created_at == latest_job_subq.c.max_created_at,
            ),
        )
        .subquery()
    )
    sources_result = await db.execute(
        select(KnowledgeSource)
        .where(KnowledgeSource.tenant_id == tenant_id)
        .order_by(KnowledgeSource.created_at.desc())
    )
    sources = list(sources_result.scalars().all())
    errors_result = await db.execute(select(latest_job_error))
    error_map = {row[0]: row[1] for row in errors_result.fetchall()}
    for source in sources:
        source.error_message = error_map.get(source.id)
    return sources


async def get_source(
    db: AsyncSession, source_id: str, tenant_id: str
) -> KnowledgeSource | None:
    result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def get_job(
    db: AsyncSession, job_id: str, tenant_id: str
) -> IngestionJob | None:
    result = await db.execute(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def get_latest_job(
    db: AsyncSession, source_id: str, tenant_id: str
) -> IngestionJob | None:
    result = await db.execute(
        select(IngestionJob)
        .where(
            IngestionJob.source_id == source_id,
            IngestionJob.tenant_id == tenant_id,
        )
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()




async def delete_source(
    db: AsyncSession, source_id: str, tenant_id: str
) -> bool:
    """Hard delete a source, its jobs, and its chunks. Returns True if deleted."""
    from sqlalchemy import delete

    # Verify source belongs to tenant first
    source = await get_source(db, source_id, tenant_id)
    if not source:
        return False

    # Delete GCS file if present
    if source.file_path:
        try:
            gcs_client = storage.Client()
            bucket = gcs_client.bucket(settings.gcs_bucket_name)
            blob = bucket.blob(source.file_path)
            blob.delete()
        except Exception:
            pass  # Do not fail the delete if GCS cleanup fails


    # Delete chunks first
    await db.execute(
        delete(KnowledgeChunk).where(
            KnowledgeChunk.source_id == source_id,
            KnowledgeChunk.tenant_id == tenant_id,
        )
    )

    # Delete jobs second
    await db.execute(
        delete(IngestionJob).where(
            IngestionJob.source_id == source_id,
            IngestionJob.tenant_id == tenant_id,
        )
    )

    # Delete source last
    await db.execute(
        delete(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.tenant_id == tenant_id,
        )
    )

    await db.flush()
    return True


async def update_source_title(
    db: AsyncSession, source_id: str, tenant_id: str, new_title: str
) -> KnowledgeSource | None:
    """Update source title. Returns updated source or None if not found."""
    result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.tenant_id == tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        return None
    
    source.title = new_title
    source.updated_at = datetime.utcnow()
    await db.flush()
    return source


async def enqueue_ingestion_job(
    db: AsyncSession, source_id: str, tenant_id: str
) -> IngestionJob:
    job = IngestionJob(
        source_id=source_id,
        tenant_id=tenant_id,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(job)
    await db.flush()

    client = tasks_v2.CloudTasksClient()
    queue_path = client.queue_path(
        settings.gcp_project_id,
        settings.cloud_tasks_location,
        settings.cloud_tasks_queue,
    )
    payload = json.dumps({
        "job_id": job.id,
        "source_id": source_id,
        "tenant_id": tenant_id,
    })
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{settings.worker_service_url}/tasks/ingestion",
            "headers": {"Content-Type": "application/json"},
            "body": payload.encode(),
            "oidc_token": {
                "service_account_email": (
                    f"naqla-worker-sa@{settings.gcp_project_id}.iam.gserviceaccount.com"
                )
            },
        }
    }
    client.create_task(request={"parent": queue_path, "task": task})
    return job
