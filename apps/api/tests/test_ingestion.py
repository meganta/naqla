import os
import sys

import pytest

# Add packages to path for local testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages"))

from modules.ingestion.models import (
    ALL_SOURCE_TYPES,
    FILE_SOURCE_TYPES,
    JOB_STATUSES,
    SOURCE_STATUSES,
    TEXT_SOURCE_TYPES,
    UNSUPPORTED_SOURCE_TYPES,
)

pytestmark = pytest.mark.asyncio

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://naqla:naqla@localhost:5432/naqla_test",
)
NEEDS_DB = pytest.mark.skipif(
    "localhost" in DB_URL and os.environ.get("CI") != "true",
    reason="skipped locally — requires postgres",
)


# ── Static/unit tests (no DB needed) ──────────────────────────────────────────

def test_health():
    from fastapi.testclient import TestClient

    from main import app
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_source_type_sets():
    assert "pdf" in FILE_SOURCE_TYPES
    assert "text" in TEXT_SOURCE_TYPES
    assert "manual" in TEXT_SOURCE_TYPES
    assert "youtube" not in FILE_SOURCE_TYPES
    assert "facebook" in UNSUPPORTED_SOURCE_TYPES
    assert ALL_SOURCE_TYPES == (
        FILE_SOURCE_TYPES | TEXT_SOURCE_TYPES
        | {"youtube", "youtube_channel"}
        | UNSUPPORTED_SOURCE_TYPES
    )


def test_status_sets():
    assert "upload_pending" in SOURCE_STATUSES
    assert "uploaded" in SOURCE_STATUSES
    assert "processed" in SOURCE_STATUSES
    assert "unsupported" in SOURCE_STATUSES
    assert "completed" in JOB_STATUSES
    assert "failed" in JOB_STATUSES


def test_chunk_arabic_text():
    from arabic_processing.chunker import chunk_arabic_text
    # Text must exceed MIN_CHUNK_CHARS (50) to produce chunks
    sentence = "\u0627\u0644\u062c\u0645\u0644\u0629 \u0627\u0644\u0641\u0639\u0644\u064a\u0629"
    text = (sentence + ". ") * 5
    chunks = chunk_arabic_text(text, source_type_tag="text")
    assert len(chunks) >= 1
    for c in chunks:
        assert "content_text" in c
        assert c["char_count"] > 0
        assert c["source_type_tag"] == "text"


def test_chunk_arabic_empty():
    from arabic_processing.chunker import chunk_arabic_text
    assert chunk_arabic_text("") == []
    assert chunk_arabic_text("   ") == []


# ── DB tests (skipped locally, run in CI) ─────────────────────────────────────

@NEEDS_DB
async def test_create_file_source_sets_upload_pending():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.database import Base
    from modules.ingestion.service import create_source
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as db:
        src = await create_source(db, "t1", "u1", "test pdf", "pdf")
        assert src.status == "upload_pending"
        assert src.tenant_id == "t1"


@NEEDS_DB
async def test_create_text_source_sets_draft():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.database import Base
    from modules.ingestion.service import create_source
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as db:
        src = await create_source(
            db, "t2", "u2", "test text", "text",
            raw_text="\u0646\u0635 \u062a\u062c\u0631\u064a\u0628\u064a",
        )
        assert src.status == "draft"
        assert src.raw_text is not None


@NEEDS_DB
async def test_create_unsupported_sets_unsupported():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.database import Base
    from modules.ingestion.service import create_source
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as db:
        src = await create_source(db, "t3", "u3", "fb post", "facebook")
        assert src.status == "unsupported"


@NEEDS_DB
async def test_create_source_unknown_type_raises():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.database import Base
    from modules.ingestion.service import create_source
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as db:
        with pytest.raises(ValueError, match="Unknown source type"):
            await create_source(db, "t4", "u4", "test", "unknown_type")


@NEEDS_DB
async def test_tenant_isolation():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.database import Base
    from modules.ingestion.service import create_source, list_sources
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as db:
        await create_source(db, "tenant_a", "u1", "doc A", "pdf")
        await create_source(db, "tenant_b", "u2", "doc B", "pdf")
        await db.commit()
    async with sf() as db:
        a = await list_sources(db, "tenant_a")
        b = await list_sources(db, "tenant_b")
        for s in a:
            assert s.tenant_id == "tenant_a"
        for s in b:
            assert s.tenant_id == "tenant_b"


@NEEDS_DB
def test_process_file_before_upload_blocked():
    from fastapi.testclient import TestClient

    from main import app
    client = TestClient(app)
    reg = client.post("/auth/register", json={
        "email": "uploadtest99@naqla.app",
        "password": "Test1234!",
        "full_name": "Test Teacher",
        "tenant_name": "Test School Upload99",
    })
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    src = client.post("/ingestion/sources", json={
        "title": "test pdf", "source_type": "pdf",
    }, headers=headers)
    assert src.status_code == 201
    source_id = src.json()["source_id"]
    assert src.json()["upload_url"] != ""
    process = client.post(
        f"/ingestion/sources/{source_id}/process", headers=headers
    )
    assert process.status_code == 422
    assert "upload" in process.json()["detail"].lower()


@NEEDS_DB
def test_text_source_process_without_upload():
    from unittest.mock import MagicMock, patch

    from fastapi.testclient import TestClient

    from main import app
    client = TestClient(app)
    reg = client.post("/auth/register", json={
        "email": "texttest99@naqla.app",
        "password": "Test1234!",
        "full_name": "Test Teacher",
        "tenant_name": "Test School Text99",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    src = client.post("/ingestion/sources", json={
        "title": "\u062f\u0631\u0633 \u0646\u062d\u0648",
        "source_type": "text",
        "raw_text": (
            "\u0627\u0644\u062c\u0645\u0644\u0629 "
            "\u0627\u0644\u0641\u0639\u0644\u064a\u0629 "
            "\u062a\u062a\u0643\u0648\u0646 \u0645\u0646 "
            "\u0641\u0639\u0644 \u0648\u0641\u0627\u0639\u0644 "
        ) * 3,
    }, headers=headers)
    assert src.status_code == 201
    source_id = src.json()["source_id"]
    assert src.json()["upload_url"] == ""
    with patch("modules.ingestion.service.tasks_v2") as mock_tasks:
        mock_client = MagicMock()
        mock_tasks.CloudTasksClient.return_value = mock_client
        mock_tasks.HttpMethod.POST = "POST"
        mock_client.queue_path.return_value = "projects/x/locations/y/queues/z"
        mock_client.create_task.return_value = MagicMock()
        process = client.post(
            f"/ingestion/sources/{source_id}/process", headers=headers
        )
        assert process.status_code == 200
        assert process.json()["status"] == "pending"
