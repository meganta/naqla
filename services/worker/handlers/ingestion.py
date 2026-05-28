import io
from datetime import datetime

from google.cloud import storage
from sqlalchemy import select


def download_file(bucket_name: str, file_path: str) -> bytes:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    return blob.download_as_bytes()


def extract_text_from_bytes(file_bytes: bytes, source_type: str) -> str:
    if source_type == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise ValueError(f"PDF extraction failed: {e}") from e

    if source_type == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise ValueError(f"DOCX extraction failed: {e}") from e

    if source_type in {"text", "manual"}:
        return file_bytes.decode("utf-8", errors="replace")

    raise ValueError(
        f"Extraction not yet implemented for source type: {source_type}. "
        "This type will be supported in a future update."
    )


async def process_ingestion_job(
    db,
    job_id: str,
    source_id: str,
    tenant_id: str,
    bucket_name: str,
) -> int:
    from arabic_processing.chunker import chunk_arabic_text
    from ingestion_models import IngestionJob, KnowledgeChunk, KnowledgeSource

    job_result = await db.execute(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.tenant_id == tenant_id,
        )
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise ValueError(f"Job {job_id} not found for tenant {tenant_id}")

    job.status = "processing"
    job.started_at = datetime.utcnow()
    await db.flush()

    source_result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.tenant_id == tenant_id,
        )
    )
    source = source_result.scalar_one_or_none()
    if not source:
        job.status = "failed"
        job.error_message = f"Source {source_id} not found for tenant {tenant_id}"
        await db.flush()
        return 0

    try:
        if source.source_type in {"text", "manual"}:
            text = source.raw_text or ""
            if not text.strip():
                raise ValueError(
                    "No text content found. Provide raw_text when creating a text/manual source."
                )
        elif source.file_path:
            file_bytes = download_file(bucket_name, source.file_path)
            text = extract_text_from_bytes(file_bytes, source.source_type)
        else:
            raise ValueError(
                f"No file_path and no raw_text for source type '{source.source_type}'. "
                "Upload the file first and call confirm-upload."
            )
    except ValueError as e:
        job.status = "failed"
        job.error_message = str(e)
        source.status = "failed"
        source.updated_at = datetime.utcnow()
        await db.flush()
        return 0

    raw_chunks = chunk_arabic_text(text, source_type_tag=source.source_type)

    for raw in raw_chunks:
        chunk = KnowledgeChunk(
            tenant_id=tenant_id,
            source_id=source_id,
            content_text=raw["content_text"],
            chunk_index=raw["chunk_index"],
            char_count=raw["char_count"],
            source_type_tag=raw["source_type_tag"],
            extra_meta=raw.get("extra_meta"),
            created_at=datetime.utcnow(),
        )
        db.add(chunk)

    job.status = "completed"
    job.chunks_created = len(raw_chunks)
    job.completed_at = datetime.utcnow()
    source.status = "processed"
    source.updated_at = datetime.utcnow()
    await db.flush()
    return len(raw_chunks)
