import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages"))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_source_type_constants():
    from modules.ingestion.models import (
        ALL_SOURCE_TYPES,
        FILE_SOURCE_TYPES,
        TEXT_SOURCE_TYPES,
        UNSUPPORTED_SOURCE_TYPES,
        URL_SOURCE_TYPES,
    )
    assert "pdf" in FILE_SOURCE_TYPES
    assert "text" in TEXT_SOURCE_TYPES
    assert "youtube" in URL_SOURCE_TYPES
    assert "facebook" in UNSUPPORTED_SOURCE_TYPES
    assert ALL_SOURCE_TYPES == (
        FILE_SOURCE_TYPES | TEXT_SOURCE_TYPES
        | URL_SOURCE_TYPES | UNSUPPORTED_SOURCE_TYPES
    )


def test_chunk_arabic_text():
    from arabic_processing.chunker import chunk_arabic_text
    sentence = "\u0627\u0644\u062c\u0645\u0644\u0629 \u0627\u0644\u0641\u0639\u0644\u064a\u0629"
    text = (sentence + ". ") * 5
    chunks = chunk_arabic_text(text, source_type_tag="text")
    assert len(chunks) >= 1
    assert all(c["char_count"] > 0 for c in chunks)


def test_chunk_arabic_empty():
    from arabic_processing.chunker import chunk_arabic_text
    assert chunk_arabic_text("") == []
