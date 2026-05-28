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

    if source_type == "pptx":
        try:
            from pptx import Presentation
            prs = Presentation(io.BytesIO(file_bytes))
            lines = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        lines.append(shape.text.strip())
            return "\n".join(lines)
        except Exception as e:
            raise ValueError(f"PPTX extraction failed: {e}") from e

    if source_type in {"text", "manual"}:
        return file_bytes.decode("utf-8", errors="replace")

    raise ValueError(
        f"Extraction not yet implemented for source type: {source_type}. "
        "This type will be supported in a future update."
    )



def extract_video_id(url: str) -> str | None:
    import re
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _fmt_seconds(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_youtube_transcript(video_id: str) -> list[dict] | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["ar", "en"]
        )
        return [
            {
                "text": t["text"],
                "start": _fmt_seconds(t["start"]),
                "end": _fmt_seconds(t["start"] + t["duration"]),
            }
            for t in transcript
        ]
    except Exception:
        return None


def chunk_transcript_with_timestamps(
    segments: list[dict],
    source_type_tag: str,
    base_meta: dict,
) -> list[dict]:
    import json
    from arabic_processing.chunker import MAX_CHUNK_CHARS, MIN_CHUNK_CHARS

    chunks = []
    current_text = ""
    current_start = None
    current_end = None
    chunk_index = 0

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        if current_start is None:
            current_start = seg.get("start", "")
        current_text = f"{current_text} {text}".strip() if current_text else text
        current_end = seg.get("end", "")
        if len(current_text) >= MAX_CHUNK_CHARS:
            meta = {**base_meta, "start_time": current_start, "end_time": current_end}
            chunks.append({
                "content_text": current_text,
                "chunk_index": chunk_index,
                "char_count": len(current_text),
                "source_type_tag": source_type_tag,
                "extra_meta": json.dumps(meta),
            })
            chunk_index += 1
            current_text = ""
            current_start = None
            current_end = None

    if current_text and len(current_text) >= MIN_CHUNK_CHARS:
        meta = {**base_meta, "start_time": current_start, "end_time": current_end}
        chunks.append({
            "content_text": current_text,
            "chunk_index": chunk_index,
            "char_count": len(current_text),
            "source_type_tag": source_type_tag,
            "extra_meta": json.dumps(meta),
        })

    return chunks


def extract_youtube_chunks(url: str, source_type: str) -> list[dict]:
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(
            f"Could not extract video ID from URL: {url}. "
            "Provide a valid YouTube video URL."
        )
    base_meta = {
        "source_type": source_type,
        "source_url": url,
        "video_id": video_id,
        "language": "ar",
    }
    segments = get_youtube_transcript(video_id)
    if not segments:
        raise ValueError(
            f"No transcript available for video {video_id}. "
            "The video must have Arabic or English captions enabled."
        )
    return chunk_transcript_with_timestamps(segments, source_type, base_meta)


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

    raw_chunks: list[dict] = []
    try:
        if source.source_type in {"text", "manual"}:
            text = source.raw_text or ""
            if not text.strip():
                raise ValueError(
                    "No text content found. Provide raw_text when creating a text/manual source."
                )
        elif source.source_type == "youtube":
            url = source.original_url or ""
            if not url:
                raise ValueError(
                    "No URL provided for YouTube source. "
                    "Set original_url when creating a youtube source."
                )
            raw_chunks = extract_youtube_chunks(url, "youtube")
            text = None
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

    if text is not None:
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
