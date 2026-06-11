"""
OCR service — GPT-4o vision provider for Arabic text extraction.
Falls back to StubOCRProvider if no OpenAI key is configured.
"""
import base64
import logging
import re
import unicodedata

import httpx
import openai

from core.config import settings

logger = logging.getLogger(__name__)

OCR_SYSTEM_PROMPT = (
    "You are an OCR engine. "
    "Extract ALL text from the image exactly as it appears, in any language. "
    "Output ONLY the extracted text — no explanations, no translations, no commentary. "
    "Preserve line breaks between separate questions or paragraphs. "
    "If the image contains no readable text at all, output exactly: [NO_TEXT]"
)


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text: strip diacritics, normalize alef variants, fix spacing."""
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    text = re.sub(r'[إأآا]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = unicodedata.normalize('NFC', text)
    return text


class OCRResult:
    def __init__(self, raw_text: str, confidence: float = 1.0, error: str | None = None):
        self.raw_text = raw_text
        self.confidence = confidence
        self.error = error

    @property
    def normalized_text(self) -> str:
        return normalize_arabic(self.raw_text)

    @property
    def is_usable(self) -> bool:
        return bool(self.normalized_text.strip()) and self.confidence >= 0.3


class BaseOCRProvider:
    async def extract_text(self, image_url: str) -> OCRResult:
        raise NotImplementedError


class GPT4oOCRProvider(BaseOCRProvider):
    """
    OCR via GPT-4o vision. Accepts:
    - Public HTTPS image URLs (passed directly)
    - GCS URLs starting with gs:// (downloaded and base64-encoded)
    """

    def __init__(self, api_key: str) -> None:
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def _image_content(self, image_url: str) -> dict:
        """
        Download image and base64-encode for GPT-4o.
        For gs:// paths: uses GCS client with ADC (avoids public access requirement).
        For public HTTPS URLs: downloads directly.
        """
        if image_url.startswith("gs://"):
            # Parse gs://bucket/path
            path_without_scheme = image_url[5:]
            bucket_name, _, blob_path = path_without_scheme.partition("/")
            try:
                import asyncio

                from google.cloud import storage as gcs
                loop = asyncio.get_event_loop()
                def _download():
                    client = gcs.Client()
                    bucket = client.bucket(bucket_name)
                    blob = bucket.blob(blob_path)
                    return blob.download_as_bytes()
                image_bytes = await loop.run_in_executor(None, _download)
                b64 = base64.b64encode(image_bytes).decode()
            except Exception as e:
                logger.error("GPT4oOCRProvider: GCS download failed: %s", e)
                raise
        else:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                image_bytes = resp.content
                b64 = base64.b64encode(image_bytes).decode()

        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
        }

    async def extract_text(self, image_url: str) -> OCRResult:
        logger.info("GPT4oOCRProvider: extracting text from image")
        try:
            image_block = await self._image_content(image_url)
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                max_tokens=1000,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": OCR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            image_block,
                            {"type": "text", "text": "استخرج كل النص الموجود في الصورة."},
                        ],
                    },
                ],
            )
            raw = response.choices[0].message.content or ""
            raw = raw.strip()

            if raw == "[NO_TEXT]" or not raw:
                logger.warning("GPT4oOCRProvider: no text found in image")
                return OCRResult(raw_text="", confidence=0.0, error="لم يُعثر على نص في الصورة")

            logger.info("GPT4oOCRProvider: extracted %d chars", len(raw))
            return OCRResult(raw_text=raw, confidence=0.9)

        except openai.BadRequestError as e:
            logger.error("GPT4oOCRProvider: bad request (image may be invalid): %s", e)
            return OCRResult(
                raw_text="", confidence=0.0,
                error="تعذّر معالجة الصورة. يرجى التقاط صورة أوضح.",
            )
        except Exception as e:
            logger.error("GPT4oOCRProvider: unexpected error: %s", e)
            return OCRResult(
                raw_text="", confidence=0.0,
                error="حدث خطأ أثناء قراءة الصورة. يرجى المحاولة مجدداً.",
            )


class StubOCRProvider(BaseOCRProvider):
    """Stub — use ocr_override in the request for testing."""
    async def extract_text(self, image_url: str) -> OCRResult:
        logger.warning("StubOCRProvider: no OCR key configured, returning empty")
        return OCRResult(raw_text="", confidence=0.0, error="OCR provider not configured")


def get_ocr_provider() -> BaseOCRProvider:
    if settings.openai_api_key:
        return GPT4oOCRProvider(api_key=settings.openai_api_key)
    logger.warning("get_ocr_provider: OPENAI_API_KEY not set, using stub")
    return StubOCRProvider()
