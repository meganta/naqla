import io
import json
import logging
import os
import tempfile
from datetime import datetime

from core.config import settings
from google.cloud import storage
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Error classification for smart retry logic
DEAD_ERROR_CODES = {
    "insufficient_quota",
    "billing_hard_limit_reached",
    "invalid_api_key",
    "account_deactivated",
}
DEAD_ERROR_MESSAGES = [
    "exceeded your current quota",
    "billing",
    "invalid api key",
    "deactivated",
    "unsupported file",
    "invalid file format",
]

def classify_error(e: Exception) -> str:
    """Returns 'dead' or 'retryable'."""
    err_str = str(e).lower()
    if hasattr(e, "code") and e.code in DEAD_ERROR_CODES:
        return "dead"
    for msg in DEAD_ERROR_MESSAGES:
        if msg in err_str:
            return "dead"
    return "retryable"

def format_user_error(e: Exception, error_type: str) -> str:
    """Returns a clear Arabic error message for the teacher."""
    err_str = str(e).lower()
    if "exceeded your current quota" in err_str or "billing" in err_str:
        return "انتهت حصة الذكاء الاصطناعي. يرجى التواصل مع الدعم الفني."
    if "invalid api key" in err_str:
        return "مفتاح API غير صالح. يرجى التواصل مع الدعم الفني."
    if "unsupported" in err_str or "invalid file format" in err_str:
        return "صيغة الملف غير مدعومة. يرجى رفع ملف بصيغة MP4 أو MP3."
    if "no content" in err_str or "produced no content" in err_str:
        return "لم يتم العثور على محتوى صوتي في الملف. تأكد أن الملف يحتوي على صوت واضح."
    if error_type == "retryable":
        return f"حدث خطأ مؤقت أثناء المعالجة. يمكنك إعادة المحاولة. ({str(e)[:100]})"
    return f"فشلت المعالجة: {str(e)[:200]}"


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def generate_embeddings(texts: list[str], api_key: str) -> list[list[float]]:
    """Generate embeddings for a list of texts using OpenAI."""
    import openai
    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------

def download_file(bucket_name: str, file_path: str) -> bytes:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    return blob.download_as_bytes()


# ---------------------------------------------------------------------------
# Text extraction (PDF / DOCX / PPTX)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Transcription provider abstraction
# ---------------------------------------------------------------------------

class TranscriptionProvider:
    """Abstract base for audio/video transcription providers."""

    def transcribe(self, file_bytes: bytes, source_type: str) -> list[dict]:
        """
        Transcribe audio/video bytes.
        Returns list of segments: [{"text": str, "start": "HH:MM:SS", "end": "HH:MM:SS"}]
        Raises ValueError on failure.
        """
        raise NotImplementedError


class WhisperTranscriptionProvider(TranscriptionProvider):
    """OpenAI Whisper transcription provider."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def transcribe(
        self,
        file_bytes: bytes,
        source_type: str,
        completed_chunks: list[dict] | None = None,
        on_chunk_complete: callable | None = None,
    ) -> list[dict]:
        """
        Transcribe audio/video file using Whisper.
        - completed_chunks: previously saved segments from a prior partial run (for resume)
        - on_chunk_complete: callback(chunk_index, segments) called after each chunk succeeds
        """
        import openai
        import subprocess
        client = openai.OpenAI(api_key=self.api_key)
        ext = "mp3" if source_type == "audio" else "mp4"
        suffix = f".{ext}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            # Extract audio as mp3 using ffmpeg
            audio_path = tmp_path + ".mp3"
            subprocess.run(
                ["ffmpeg", "-i", tmp_path, "-vn", "-acodec", "libmp3lame",
                 "-ar", "16000", "-ac", "1", "-b:a", "32k", "-y", audio_path],
                check=True, capture_output=True
            )
            os.unlink(tmp_path)
            # Split into chunks if over 20MB
            max_bytes = 20 * 1024 * 1024
            audio_size = os.path.getsize(audio_path)
            if audio_size <= max_bytes:
                chunk_paths = [audio_path]
                chunk_offsets = [0.0]
            else:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                    capture_output=True, text=True, check=True
                )
                duration = float(result.stdout.strip())
                num_chunks = int(audio_size / max_bytes) + 1
                chunk_duration = duration / num_chunks
                chunk_paths = []
                chunk_offsets = []
                for i in range(num_chunks):
                    start = i * chunk_duration
                    chunk_path = audio_path + f".chunk{i}.mp3"
                    subprocess.run(
                        ["ffmpeg", "-i", audio_path, "-ss", str(start),
                         "-t", str(chunk_duration), "-y", chunk_path],
                        check=True, capture_output=True
                    )
                    chunk_paths.append(chunk_path)
                    chunk_offsets.append(start)
                os.unlink(audio_path)
            total_chunks = len(chunk_paths)
            logger.info("Transcribing %d audio chunk(s) with Whisper", total_chunks)
            # Build map of already completed chunks (for resume)
            completed_map: dict[int, list[dict]] = {}
            if completed_chunks:
                for item in completed_chunks:
                    completed_map[item["chunk_index"]] = item["segments"]
                logger.info(
                    "Resuming transcription: %d/%d chunks already done",
                    len(completed_map), total_chunks
                )
            all_segments = []
            try:
                for idx, (chunk_path, offset) in enumerate(zip(chunk_paths, chunk_offsets)):
                    # Resume: skip already completed chunks
                    if idx in completed_map:
                        logger.info("Skipping chunk %d/%d (already transcribed)", idx + 1, total_chunks)
                        all_segments.extend(completed_map[idx])
                        continue
                    logger.info("Transcribing chunk %d/%d (offset=%.1fs)", idx + 1, total_chunks, offset)
                    with open(chunk_path, "rb") as audio_file:
                        response = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language="ar",
                            response_format="verbose_json",
                            timestamp_granularities=["segment"],
                        )
                    chunk_segments = []
                    for seg in (response.segments or []):
                        chunk_segments.append({
                            "text": seg.text.strip(),
                            "start": _seconds_to_time(seg.start + offset),
                            "end": _seconds_to_time(seg.end + offset),
                        })
                    if not chunk_segments and response.text:
                        chunk_segments.append({
                            "text": response.text.strip(),
                            "start": _seconds_to_time(offset),
                            "end": _seconds_to_time(offset),
                        })
                    all_segments.extend(chunk_segments)
                    logger.info(
                        "Chunk %d/%d done: %d segments", idx + 1, total_chunks, len(chunk_segments)
                    )
                    # Save progress via callback
                    if on_chunk_complete:
                        on_chunk_complete(idx, chunk_segments)
            finally:
                for p in chunk_paths:
                    if os.path.exists(p):
                        os.unlink(p)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        if not all_segments:
            raise ValueError("Whisper transcription produced no content.")
        logger.info("Transcription complete: %d total segments", len(all_segments))
        return all_segments


def _seconds_to_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_transcription_provider(source_type: str, openai_api_key: str) -> TranscriptionProvider:
    """
    Return the appropriate transcription provider for uploaded audio/video files.
    Raises ValueError if no provider is available.
    """
    if not openai_api_key:
        raise ValueError(
            "OpenAI API key is not configured. "
            "Set OPENAI_API_KEY in worker environment to enable audio/video transcription."
        )
    return WhisperTranscriptionProvider(api_key=openai_api_key)


# ---------------------------------------------------------------------------
# YouTube helpers
# ---------------------------------------------------------------------------

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


NO_CAPTIONS_MESSAGE = (
    "لا يوجد تفريغ نصي أو ترجمة متاحة لهذا الفيديو على YouTube. "
    "إذا كنت مالك الفيديو، يمكنك إضافة الترجمة من YouTube Studio دون إعادة رفع الفيديو: "
    "افتح YouTube Studio، ثم Subtitles، اختر الفيديو، أضف اللغة، "
    "ثم أضف الترجمة عبر رفع ملف ترجمة أو استخدام Auto-sync أو الكتابة اليدوية. "
    "بعد إضافة الترجمة، أعد محاولة الاستيراد في نقلة. "
    "أو يمكنك رفع ملف الفيديو/الصوت الأصلي مباشرة إلى نقلة ليتم تفريغه بالذكاء الاصطناعي."
)


async def get_google_access_token(db, tenant_id: str) -> str | None:
    from datetime import timezone
    from ingestion_models import TenantSettings
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    ts = result.scalar_one_or_none()
    if not ts:
        logger.warning("No tenant settings found for tenant %s", tenant_id)
        return None
    if not ts.google_access_token:
        logger.warning("No Google access token for tenant %s", tenant_id)
        return None
    # Refresh if expired
    if ts.google_token_expiry:
        expiry = ts.google_token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        from datetime import timedelta
        if datetime.now(timezone.utc) >= expiry - timedelta(minutes=5):
            import httpx
            resp = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": ts.google_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code == 200:
                token_data = resp.json()
                ts.google_access_token = token_data["access_token"]
                from datetime import timedelta as td
                ts.google_token_expiry = datetime.utcnow() + td(
                    seconds=token_data.get("expires_in", 3600)
                )
                await db.commit()
            else:
                return None
    return ts.google_access_token


async def get_youtube_transcript_oauth(
    video_id: str, access_token: str
) -> list[dict] | None:
    import httpx
    headers = {"Authorization": f"Bearer {access_token}"}
    # List available caption tracks
    list_url = "https://www.googleapis.com/youtube/v3/captions"
    resp = httpx.get(
        list_url,
        params={"part": "snippet", "videoId": video_id},
        headers=headers,
    )
    if resp.status_code != 200:
        logger.error("Failed to list captions for %s: %s", video_id, resp.text)
        return None
    items = resp.json().get("items", [])
    if not items:
        return None
    # Prefer Arabic, then English
    caption_id = None
    for lang in ["ar", "en"]:
        for item in items:
            if item["snippet"]["language"] == lang:
                caption_id = item["id"]
                break
        if caption_id:
            break
    if not caption_id:
        caption_id = items[0]["id"]
    # Download caption track (SRT format)
    dl_url = f"https://www.googleapis.com/youtube/v3/captions/{caption_id}"
    resp = httpx.get(
        dl_url,
        params={"tfmt": "srt"},
        headers=headers,
    )
    if resp.status_code != 200:
        logger.error("Failed to download caption %s: %s", caption_id, resp.text)
        return None
    # Parse SRT into segments
    segments = []
    blocks = resp.text.strip().split(chr(10)+chr(10))
    for block in blocks:
        lines = block.strip().split(chr(10))
        if len(lines) < 3:
            continue
        # lines[0] = index, lines[1] = timestamps, lines[2+] = text
        timestamp_line = lines[1]
        text = " ".join(lines[2:]).strip()
        if not text:
            continue
        try:
            start_str = timestamp_line.split(" --> ")[0].strip()
            h, m, s = start_str.replace(",", ".").split(":")
            start_sec = int(h) * 3600 + int(m) * 60 + float(s)
            end_str = timestamp_line.split(" --> ")[1].strip()
            h, m, s = end_str.replace(",", ".").split(":")
            end_sec = int(h) * 3600 + int(m) * 60 + float(s)
            segments.append({
                "text": text,
                "start": _fmt_seconds(start_sec),
                "end": _fmt_seconds(end_sec),
            })
        except Exception:
            continue
    return segments if segments else None


def get_youtube_transcript_supadata(video_id: str) -> list[dict] | None:
    if not settings.supadata_api_key:
        return None
    try:
        import httpx
        url = f"https://www.youtube.com/watch?v={video_id}"
        resp = httpx.get(
            "https://api.supadata.ai/v1/youtube/transcript",
            params={"url": url, "text": "false"},
            headers={"x-api-key": settings.supadata_api_key},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.error("Supadata failed for %s: %s", video_id, resp.text)
            return None
        data = resp.json()
        segments = data.get("content", [])
        if not segments:
            return None
        return [
            {
                "text": s.get("text", ""),
                "start": _fmt_seconds(s.get("offset", 0) / 1000),
                "end": _fmt_seconds((s.get("offset", 0) + s.get("duration", 0)) / 1000),
            }
            for s in segments
            if s.get("text")
        ]
    except Exception as e:
        logger.error("Supadata error for %s: %s", video_id, e)
        return None


def get_youtube_transcript(video_id: str) -> list[dict] | None:
    # Try Supadata first
    segments = get_youtube_transcript_supadata(video_id)
    if segments:
        return segments
    # Fallback to youtube-transcript-api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)
        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(["ar", "en"])
        except Exception as e:
            logger.info("No manual transcript: %s", e)
        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(["ar", "en"])
            except Exception as e:
                logger.info("No generated transcript: %s", e)
        if transcript is None:
            return None
        fetched = transcript.fetch()
        return [
            {
                "text": t.text,
                "start": _fmt_seconds(t.start),
                "end": _fmt_seconds(t.start + t.duration),
            }
            for t in fetched
        ]
    except Exception as e:
        logger.error("get_youtube_transcript failed for %s: %s", video_id, e)
        return None


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


async def extract_youtube_chunks(
    url: str, source_type: str, db=None, tenant_id: str | None = None
) -> list[dict]:
    """
    Extract chunks from a YouTube video.
    Tries OAuth (YouTube Data API) first, falls back to youtube-transcript-api.
    Raises ValueError with Arabic instruction if no captions available.
    """
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
    # Try OAuth first
    if db is not None and tenant_id is not None:
        access_token = await get_google_access_token(db, tenant_id)
        if access_token:
            segments = await get_youtube_transcript_oauth(video_id, access_token)
            if segments:
                return chunk_transcript_with_timestamps(segments, source_type, base_meta)
            logger.warning("OAuth transcript failed for %s, falling back", video_id)
    # Fallback to youtube-transcript-api
    segments = get_youtube_transcript(video_id)
    if not segments:
        raise ValueError(NO_CAPTIONS_MESSAGE)
    return chunk_transcript_with_timestamps(segments, source_type, base_meta)


# ---------------------------------------------------------------------------
# YouTube channel helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main ingestion job processor
# ---------------------------------------------------------------------------

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
    text = None

    try:
        if source.source_type in {"text", "manual"}:
            text = source.raw_text or ""
            if not text.strip():
                raise ValueError(
                    "No text content found. "
                    "Provide raw_text when creating a text/manual source."
                )

        elif source.source_type == "youtube":
            url = source.original_url or ""
            if not url:
                raise ValueError(
                    "No URL provided for YouTube source. "
                    "Set original_url when creating a youtube source."
                )
            raw_chunks = await extract_youtube_chunks(url, "youtube", db=db, tenant_id=tenant_id)
            text = None

        elif source.source_type == "youtube_channel":
            url = source.original_url or ""
            if not url:
                raise ValueError(
                    "No URL or handle provided for YouTube channel source."
                )
            if not settings.youtube_api_key:
                raise ValueError(
                    "YouTube Data API key is not configured. "
                    "Set YOUTUBE_API_KEY in worker environment."
                )
            channel_id = (
                url.replace("https://www.youtube.com/", "")
                .replace("https://youtube.com/", "")
            )
            if channel_id.startswith("@"):
                channel_id = channel_id[1:]
            video_ids = get_channel_video_ids(
                channel_id, settings.youtube_api_key,
                settings.youtube_channel_max_videos,
            )
            if not video_ids:
                raise ValueError(f"No videos found for channel: {channel_id}")
            raw_chunks = [
                {
                    "content_text": (
                        f"YouTube video: https://www.youtube.com/watch?v={vid}"
                    ),
                    "chunk_index": i,
                    "char_count": len(
                        f"https://www.youtube.com/watch?v={vid}"
                    ) + 20,
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
            if not source.file_path:
                raise ValueError(
                    f"No file uploaded for {source.source_type} source. "
                    "Upload the file first and call confirm-upload."
                )
            # Load resume progress from extra_meta
            completed_chunks = None
            if source.extra_meta:
                try:
                    meta = json.loads(source.extra_meta)
                    if meta.get("transcription_progress"):
                        completed_chunks = meta["transcription_progress"]
                        logger.info(
                            "Found %d previously completed chunks for source %s",
                            len(completed_chunks), source_id
                        )
                except Exception:
                    pass
            file_bytes = download_file(bucket_name, source.file_path)
            provider = get_transcription_provider(
                source.source_type, settings.openai_api_key
            )
            # Callback to save progress after each chunk
            async def save_chunk_progress(chunk_index: int, chunk_segments: list[dict]) -> None:
                try:
                    existing_meta = {}
                    if source.extra_meta:
                        existing_meta = json.loads(source.extra_meta)
                    progress = existing_meta.get("transcription_progress", [])
                    progress.append({"chunk_index": chunk_index, "segments": chunk_segments})
                    existing_meta["transcription_progress"] = progress
                    source.extra_meta = json.dumps(existing_meta, ensure_ascii=False)
                    source.updated_at = datetime.utcnow()
                    await db.flush()
                    logger.info("Saved progress for chunk %d", chunk_index)
                except Exception as e:
                    logger.warning("Failed to save chunk progress: %s", e)
            def sync_callback(chunk_index: int, chunk_segments: list[dict]) -> None:
                import asyncio
                asyncio.get_event_loop().run_until_complete(
                    save_chunk_progress(chunk_index, chunk_segments)
                )
            segments = provider.transcribe(
                file_bytes,
                source.source_type,
                completed_chunks=completed_chunks,
                on_chunk_complete=sync_callback,
            )
            # Clear transcription progress after full success
            if source.extra_meta:
                try:
                    meta = json.loads(source.extra_meta)
                    meta.pop("transcription_progress", None)
                    source.extra_meta = json.dumps(meta, ensure_ascii=False) if meta else None
                except Exception:
                    pass
            base_meta = {
                "source_type": source.source_type,
                "file_path": source.file_path,
                "transcription_provider": "whisper",
            }
            raw_chunks = chunk_transcript_with_timestamps(
                segments, source.source_type, base_meta
            )
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
        logger.exception(
            "Ingestion failed job=%s source=%s: %s", job_id, source_id, e
        )
        job.status = "failed"
        job.error_message = str(e)
        source.status = "failed"
        source.updated_at = datetime.utcnow()
        await db.flush()
        return 0

    if text is not None:
        raw_chunks = chunk_arabic_text(text, source_type_tag=source.source_type)

    # Generate embeddings if OpenAI key is available
    embeddings: list[list[float]] = []
    if raw_chunks and settings.openai_api_key:
        try:
            texts = [r["content_text"] for r in raw_chunks]
            for i in range(0, len(texts), 100):
                batch = texts[i:i + 100]
                batch_embeddings = generate_embeddings(batch, settings.openai_api_key)
                embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.warning("Embedding generation failed: %s", e)
            embeddings = []

    for i, raw in enumerate(raw_chunks):
        chunk = KnowledgeChunk(
            tenant_id=tenant_id,
            source_id=source_id,
            content_text=raw["content_text"],
            chunk_index=raw["chunk_index"],
            char_count=raw["char_count"],
            source_type_tag=raw["source_type_tag"],
            extra_meta=raw.get("extra_meta"),
            embedding=embeddings[i] if i < len(embeddings) else None,
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
