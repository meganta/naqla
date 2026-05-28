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
        src = await create_source(
            db,
            "3da37e3a-0c40-410b-b914-f6344fb2599a",
            "e39a6e35-4e2f-42db-9af9-9f46ff24a386",
            "test pdf",
            "pdf",
        )
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
            db,
            "23696a35-27b8-47ff-8eaa-541d7d89b68b",
            "c8e79fb1-e2bc-40e6-81f6-87930666fbbd",
            "test text",
            "text",
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
        src = await create_source(
            db,
            "0def021b-ca05-4864-b87d-5de622d5b010",
            "49ef7fff-60b0-4aa6-ab44-aa077c956a01",
            "fb post",
            "facebook",
        )
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
        await create_source(db, "e20281dd-92e8-41a6-9fdb-c9c3183efc7b", "u1", "doc A", "pdf")
        await create_source(db, "0d20d5ba-fa1b-4813-a1ee-338ef0688c45", "u2", "doc B", "pdf")
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
    import httpx
    base = "https://naqla-api-dev-uagnx6q44q-ew.a.run.app"
    import random
    import time
    email = f"ci_upload_{int(time.time())}_{random.randint(1000,9999)}@naqla.app"
    reg = httpx.post(f"{base}/auth/register", json={
        "email": email, "password": "Test1234!",
        "full_name": "CI Teacher", "tenant_name": f"CI School {email}",
    }, timeout=30)
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    src = httpx.post(f"{base}/ingestion/sources",
        json={"title": "ci pdf", "source_type": "pdf"},
        headers=headers, timeout=30)
    assert src.status_code == 201
    source_id = src.json()["source_id"]
    assert src.json()["upload_url"] != ""
    process = httpx.post(
        f"{base}/ingestion/sources/{source_id}/process",
        headers=headers, timeout=30)
    assert process.status_code == 422
    assert "upload" in process.json()["detail"].lower()


@NEEDS_DB
def test_text_source_process_without_upload():
    import random
    import time

    import httpx
    base = "https://naqla-api-dev-uagnx6q44q-ew.a.run.app"
    email = f"ci_text_{int(time.time())}_{random.randint(1000,9999)}@naqla.app"
    reg = httpx.post(f"{base}/auth/register", json={
        "email": email, "password": "Test1234!",
        "full_name": "CI Teacher", "tenant_name": f"CI School {email}",
    }, timeout=30)
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    raw = (
        "\u0627\u0644\u062c\u0645\u0644\u0629 "
        "\u0627\u0644\u0641\u0639\u0644\u064a\u0629 "
        "\u062a\u062a\u0643\u0648\u0646 \u0645\u0646 "
        "\u0641\u0639\u0644 \u0648\u0641\u0627\u0639\u0644. "
    ) * 5
    src = httpx.post(f"{base}/ingestion/sources", json={
        "title": "ci text", "source_type": "text", "raw_text": raw,
    }, headers=headers, timeout=30)
    assert src.status_code == 201
    source_id = src.json()["source_id"]
    assert src.json()["upload_url"] == ""
    process = httpx.post(
        f"{base}/ingestion/sources/{source_id}/process",
        headers=headers, timeout=30)
    assert process.status_code == 200
    assert process.json()["status"] == "pending"
