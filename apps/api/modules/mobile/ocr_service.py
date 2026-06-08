"""
OCR service abstraction.
Default provider: stub (returns empty text, for testing pass ocr_override).
TODO: replace StubOCRProvider with a real Arabic-capable OCR provider
      e.g. Google Vision API or Azure Computer Vision.
"""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text: strip diacritics, normalize alef variants, fix spacing."""
    # Remove Arabic diacritics (tashkeel)
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    # Normalize alef variants to plain alef
    text = re.sub(r'[إأآا]', 'ا', text)
    # Normalize teh marbuta
    text = re.sub(r'ة', 'ه', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # NFC normalization
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


class StubOCRProvider(BaseOCRProvider):
    """
    Stub OCR provider — always returns empty text.
    Use ocr_override in the request to inject text during development/testing.
    TODO: replace with a real Arabic OCR provider.
    """
    async def extract_text(self, image_url: str) -> OCRResult:
        logger.warning("StubOCRProvider: no real OCR configured, returning empty text")
        return OCRResult(raw_text="", confidence=0.0, error="OCR provider not configured")


# TODO: implement GoogleVisionOCRProvider
# class GoogleVisionOCRProvider(BaseOCRProvider):
#     async def extract_text(self, image_url: str) -> OCRResult:
#         ...


def get_ocr_provider() -> BaseOCRProvider:
    """
    Factory — returns the configured OCR provider.
    TODO: read from settings.ocr_provider once a real provider is implemented.
    """
    return StubOCRProvider()
