import io
from datetime import datetime

from google.cloud import storage


def download_file(bucket_name: str, file_path: str) -> bytes:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    return blob.download_as_bytes()


def extract_text(file_bytes: bytes, source_type: str) -> str:
    if source_type == "pdf":
        try:
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise ValueError(f"PDF extraction failed: {e}") from e

    if source_type in {"docx"}:
        try:
            import docx

            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise ValueError(f"DOCX extraction failed: {e}") from e

    if source_type == "text":
        return file_bytes.decode("utf-8", errors="replace")

    return file_bytes.decode("utf-8", errors="replace")


async def process_ingestion_job(
    db,
    job_id: str,
    source_id: str,
    tenant_id: str,
    bucket_name: str,
) -> int:
    from sqlalchemy import select

    from arabic_processing.chunker import chunk_arabic_text
    from ingestion_models import IngestionJob, KnowledgeChunk, KnowledgeSource

    job_result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise ValueError(f"Job {job_id} not found")

    job.status = "processing"
    job.started_at = datetime.utcnow()
    await db.flush()

    source_result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id == source_id)
    )
    source = source_result.scalar_one_or_none()
    if not source or not source.file_path:
        job.status = "failed"
        job.error_message = "Source or file path not found"
        await db.flush()
        return 0

    file_bytes = download_file(bucket_name, source.file_path)
    text = extract_text(file_bytes, source.source_type)

    raw_chunks = chunk_arabic_text(text, source_type_tag=source.source_type)

    for raw in raw_chunks:
        chunk = KnowledgeChunk(
            tenant_id=tenant_id,
            source_id=source_id,
            content_text=raw["content_text"],
            chunk_index=raw["chunk_index"],
            char_count=raw["char_count"],
            source_type_tag=raw["source_type_tag"],
            created_at=datetime.utcnow(),
        )
        db.add(chunk)

    job.status = "done"
    job.chunks_created = len(raw_chunks)
    job.completed_at = datetime.utcnow()
    source.status = "processed"
    await db.flush()

    return len(raw_chunks)
