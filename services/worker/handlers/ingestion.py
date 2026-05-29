import io
import json
import logging
from datetime import datetime

from google.cloud import storage
from sqlalchemy import select

logger = logging.getLogger(__name__)


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
            document = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in document.paragraphs if p.text.strip())
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
        r"shorts/([A-Za-z0-9_-]{11})",
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


def transcribe_youtube_with_gemini(video_id: str, api_key: str) -> str:
    """Transcribe a YouTube video using Gemini's native video understanding."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    url = f"https://www.youtube.com/watch?v={video_id}"
    prompt = (
        "Please transcribe the spoken content of this video in full. "
        "If the video is in Arabic, transcribe in Arabic. "
        "If in English, transcribe in English. "
        "Output only the transcription text, no timestamps or labels."
    )
    response = model.generate_content(
        [url, prompt],
        generation_config=genai.types.GenerationConfig(max_output_tokens=8192),
    )
    return response.text or ""


def chunk_transcript_with_timestamps(
    segments: list[dict],
    source_type_tag: str,
    base_meta: dict,
) -> list[dict]:
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


def extract_youtube_chunks_with_fallback(
    url: str, source_type: str, api_key: str | None = None
) -> list[dict]:
    """Try captions first, fallback to Whisper transcription if no captions."""
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

    # Try captions first
    segments = get_youtube_transcript(video_id)
    if segments:
        return chunk_transcript_with_timestamps(segments, source_type, base_meta)

    # Fallback: transcribe using Gemini native video understanding
    if not api_key:
        raise ValueError(
            f"No transcript available for video {video_id} and "
            "no Gemini API key configured for transcription fallback."
        )

    try:
        transcribed_text = transcribe_youtube_with_gemini(video_id, api_key)
    except Exception as e:
        raise ValueError(
            f"Gemini transcription failed for video {video_id}: {e}"
        ) from e

    if not transcribed_text.strip():
        raise ValueError(
            f"Transcription produced no text for video {video_id}."
        )

    # Chunk the transcribed text (no timestamps available from Whisper)
    from arabic_processing.chunker import chunk_arabic_text
    chunks = chunk_arabic_text(transcribed_text, source_type_tag=source_type)
    for chunk in chunks:
        chunk["extra_meta"] = json.dumps({
            **base_meta,
            "transcribed": True,
            "transcription_provider": "openai_whisper",
        })
    return chunks


def get_channel_video_ids(
    channel_identifier: str, api_key: str, max_videos: int = 25
) -> list[str]:
    """Discover video IDs from a YouTube channel using Data API v3."""
    import httpx

    channel_id = None
    if channel_identifier.startswith("UC") and len(channel_identifier) == 24:
        channel_id = channel_identifier
    else:
        search_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": channel_identifier,
            "type": "channel",
            "maxResults": 1,
            "key": api_key,
        }
        resp = httpx.get(search_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            raise ValueError(f"Could not find YouTube channel: {channel_identifier}")
        channel_id = items[0]["snippet"]["channelId"]

    channel_url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "contentDetails",
        "id": channel_id,
        "key": api_key,
    }
    resp = httpx.get(channel_url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items", [])
    if not items:
        raise ValueError(f"Could not retrieve channel details for {channel_id}")

    uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids = []
    playlist_url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": min(max_videos, 50),
        "key": api_key,
    }
    resp = httpx.get(playlist_url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("items", []):
        video_ids.append(item["contentDetails"]["videoId"])
        if len(video_ids) >= max_videos:
            break

    return video_ids


async def process_ingestion_job(
    db,
    job_id: str,
    source_id: str,
    tenant_id: str,
    bucket_name: str,
) -> int:
    from arabic_processing.chunker import chunk_arabic_text
    from core.config import settings
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
    text = None

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
            raw_chunks = extract_youtube_chunks_with_fallback(
                url, "youtube", api_key=settings.gemini_api_key or None
            )
            text = None

        elif source.source_type == "youtube_channel":
            url = source.original_url or ""
            if not url:
                raise ValueError(
                    "No URL or handle provided for YouTube channel source. "
                    "Set original_url when creating a youtube_channel source."
                )
            if not settings.youtube_api_key:
                raise ValueError(
                    "YouTube Data API key is not configured. "
                    "Set YOUTUBE_API_KEY in worker environment."
                )
            channel_id = url.replace("https://www.youtube.com/", "").replace("https://youtube.com/", "")
            if channel_id.startswith("@"):
                channel_id = channel_id[1:]
            video_ids = get_channel_video_ids(
                channel_id, settings.youtube_api_key, settings.youtube_channel_max_videos
            )
            if not video_ids:
                raise ValueError(f"No videos found for channel: {channel_id}")
            raw_chunks = [
                {
                    "content_text": f"YouTube video: https://www.youtube.com/watch?v={vid}",
                    "chunk_index": i,
                    "char_count": len(f"https://www.youtube.com/watch?v={vid}") + 20,
                    "source_type_tag": "youtube_channel",
                    "extra_meta": json.dumps({
                        "video_id": vid,
                        "channel_identifier": channel_id,
                        "index": i,
                    }),
                }
                for i, vid in enumerate(video_ids)
            ]
            text = None

        elif source.source_type in {"audio", "video"}:
            raise ValueError(
                f"Source type '{source.source_type}' requires transcription. "
                "Audio/video transcription is not yet implemented."
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
        logger.exception("Ingestion failed job=%s source=%s: %s", job_id, source_id, e)
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
