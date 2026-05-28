import json
from datetime import datetime, timedelta

from google.cloud import storage, tasks_v2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.ingestion.models import IngestionJob, KnowledgeSource

ALLOWED_SOURCE_TYPES = {
    "pdf", "docx", "pptx", "text", "audio", "video", "youtube", "manual"
}


def generate_signed_upload_url(
    source_id: str, source_type: str, tenant_id: str
) -> tuple[str, str]:
    client = storage.Client()
    bucket = client.bucket(settings.gcs_bucket_name)
    extension_map = {
        "pdf": "pdf",
        "docx": "docx",
        "pptx": "pptx",
        "audio": "mp3",
        "video": "mp4",
        "text": "txt",
    }
    ext = extension_map.get(source_type, "bin")
    file_path = f"uploads/{tenant_id}/{source_id}.{ext}"
    blob = bucket.blob(file_path)
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=15),
        method="PUT",
        content_type="application/octet-stream",
    )
    return upload_url, file_path


async def create_source(
    db: AsyncSession,
    tenant_id: str,
    teacher_id: str,
    title: str,
    source_type: str,
    original_url: str | None = None,
) -> KnowledgeSource:
    source = KnowledgeSource(
        tenant_id=tenant_id,
        teacher_id=teacher_id,
        title=title,
        source_type=source_type,
        original_url=original_url,
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(source)
    await db.flush()
    return source


async def list_sources(db: AsyncSession, tenant_id: str) -> list[KnowledgeSource]:
    result = await db.execute(
        select(KnowledgeSource)
        .where(KnowledgeSource.tenant_id == tenant_id)
        .order_by(KnowledgeSource.created_at.desc())
    )
    return list(result.scalars().all())


async def get_job(db: AsyncSession, job_id: str, tenant_id: str) -> IngestionJob | None:
    result = await db.execute(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def enqueue_ingestion_job(
    db: AsyncSession, source_id: str, tenant_id: str
) -> IngestionJob:
    job = IngestionJob(
        source_id=source_id,
        tenant_id=tenant_id,
        status="queued",
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
    payload = json.dumps({"job_id": job.id, "source_id": source_id, "tenant_id": tenant_id})
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
